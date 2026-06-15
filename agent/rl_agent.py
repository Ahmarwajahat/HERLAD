import os
import torch
import torch.nn as nn
import torch.optim as optim
import torch.nn.functional as F

# Action mapping for the LLM providers
ACTION_MAP = {
    "Groq-Key1-70b": 0,
    "Groq-Key2-70b": 1,
    "Groq-Key3-70b": 2,
    "SambaNova-70b": 3,
    "Cerebras-70b": 4,
    "OpenRouter-Key2": 5,
    "OpenRouter-Key3": 6
}
REV_ACTION_MAP = {v: k for k, v in ACTION_MAP.items()}

MODEL_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "ppo_agent.pt")

class ActorCritic(nn.Module):
    def __init__(self, state_dim=2, action_dim=7):
        super(ActorCritic, self).__init__()
        self.actor = nn.Sequential(
            nn.Linear(state_dim, 32),
            nn.ReLU(),
            nn.Linear(32, action_dim)
        )
        self.critic = nn.Sequential(
            nn.Linear(state_dim, 32),
            nn.ReLU(),
            nn.Linear(32, 1)
        )

class RLAgent:
    def __init__(self, lr=0.01, clip_eps=0.2, c1=0.5, c2=0.01):
        self.state_dim = 2
        self.action_dim = len(ACTION_MAP)
        self.clip_eps = clip_eps
        self.c1 = c1  # Value loss coefficient
        self.c2 = c2  # Entropy coefficient
        
        self.model = ActorCritic(self.state_dim, self.action_dim)
        self.optimizer = optim.Adam(self.model.parameters(), lr=lr)
        
        # Temporary buffers for online learning updates
        self.last_state_tensor = None
        self.last_action_idx = None
        self.last_log_prob = None
        self.last_value = None
        
        self.load_model()

    def load_model(self):
        if os.path.exists(MODEL_FILE):
            try:
                checkpoint = torch.load(MODEL_FILE, map_location="cpu")
                self.model.load_state_dict(checkpoint["model_state_dict"])
                self.optimizer.load_state_dict(checkpoint["optimizer_state_dict"])
                print(f"[PPO Agent]: Loaded model parameters from {MODEL_FILE}")
            except Exception as e:
                print(f"[PPO Agent]: Error loading model checkpoint: {e}")

    def save_model(self):
        try:
            torch.save({
                "model_state_dict": self.model.state_dict(),
                "optimizer_state_dict": self.optimizer.state_dict(),
            }, MODEL_FILE)
        except Exception as e:
            print(f"[PPO Agent]: Error saving model checkpoint: {e}")

    def _get_state_tensor(self, state_str):
        # State: "simple" or "complex"
        if state_str == "simple":
            return torch.tensor([1.0, 0.0], dtype=torch.float32)
        else:
            return torch.tensor([0.0, 1.0], dtype=torch.float32)

    def choose_action(self, state, available_actions):
        if not available_actions:
            return None
            
        state_tensor = self._get_state_tensor(state)
        
        self.model.eval()
        with torch.no_grad():
            logits = self.model.actor(state_tensor)
            value = self.model.critic(state_tensor)
            
        # Apply action masking for unconfigured/dead providers
        mask = torch.full_like(logits, -1e9)
        for act in available_actions:
            if act in ACTION_MAP:
                idx = ACTION_MAP[act]
                mask[idx] = 0.0
                
        masked_logits = logits + mask
        probs = F.softmax(masked_logits, dim=-1)
        
        # Sample action from the probability distribution (stochastic policy)
        dist = torch.distributions.Categorical(probs)
        sample_tensor = dist.sample()
        action_idx = int(sample_tensor.item())
        log_prob = float(dist.log_prob(sample_tensor).item())
        
        chosen_action = REV_ACTION_MAP.get(action_idx, available_actions[0])
        
        # Cache transaction details for the next policy update step
        self.last_state_tensor = state_tensor
        self.last_action_idx = action_idx
        self.last_log_prob = log_prob
        self.last_value = value.item()
        
        print(f"[PPO Agent]: Selected action '{chosen_action}' for state '{state}' (Probability: {probs[action_idx].item():.2%})")
        return chosen_action

    def update_q_value(self, state, action, reward):
        # Wrap update_q_value function signature to perform PPO gradient updates online
        if self.last_state_tensor is None or self.last_action_idx is None:
            return
            
        state_tensor = self.last_state_tensor
        action_idx = torch.tensor(self.last_action_idx, dtype=torch.long)
        old_log_prob = torch.tensor(self.last_log_prob, dtype=torch.float32)
        old_val = self.last_value
        
        self.model.train()
        
        logits = self.model.actor(state_tensor)
        value = self.model.critic(state_tensor)
        
        # Apply action masking to preserve correct probability distributions
        mask = torch.full_like(logits, -1e9)
        for act in ACTION_MAP:
            mask[ACTION_MAP[act]] = 0.0
            
        masked_logits = logits + mask
        probs = F.softmax(masked_logits, dim=-1)
        
        dist = torch.distributions.Categorical(probs)
        new_log_prob = dist.log_prob(action_idx)
        entropy = dist.entropy()
        
        # Advantage estimation: A(s,a) = Reward - Value(s)
        advantage = reward - old_val
        
        # Probability ratio r(theta)
        ratio = torch.exp(new_log_prob - old_log_prob)
        
        # Clipped surrogate objective
        surr1 = ratio * advantage
        surr2 = torch.clamp(ratio, 1.0 - self.clip_eps, 1.0 + self.clip_eps) * advantage
        
        policy_loss = -torch.min(surr1, surr2)
        value_loss = F.mse_loss(value, torch.tensor([reward], dtype=torch.float32))
        
        # Combined objective loss
        loss = policy_loss + self.c1 * value_loss - self.c2 * entropy
        
        self.optimizer.zero_grad()
        loss.backward()
        self.optimizer.step()
        
        self.save_model()
        action_name = REV_ACTION_MAP.get(self.last_action_idx, "unknown")
        print(f"[PPO Agent]: Updated policy on action '{action_name}'! Total Loss: {loss.item():.4f}, Policy Loss: {policy_loss.item():.4f}, Value Loss: {value_loss.item():.4f}")
        
        # Clear transaction cache
        self.last_state_tensor = None
        self.last_action_idx = None
        self.last_log_prob = None
        self.last_value = None
