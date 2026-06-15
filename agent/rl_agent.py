import os
import json
import random

Q_TABLE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "rl_q_table.json")

class RLAgent:
    def __init__(self, alpha=0.2, gamma=0.0, epsilon=0.15):
        self.alpha = alpha      # Learning rate
        self.gamma = gamma      # Discount factor (0 for single-step bandit tasks)
        self.epsilon = epsilon  # Exploration rate
        self.q_table = {}       # State -> {Action -> Value}
        self.load_q_table()

    def load_q_table(self):
        if os.path.exists(Q_TABLE_FILE):
            try:
                with open(Q_TABLE_FILE, "r") as f:
                    self.q_table = json.load(f)
                print(f"[RL Agent]: Loaded Q-table from {Q_TABLE_FILE}")
            except Exception as e:
                print(f"[RL Agent]: Error loading Q-table: {e}")
                self.q_table = {}
        else:
            self.q_table = {}

    def save_q_table(self):
        try:
            with open(Q_TABLE_FILE, "w") as f:
                json.dump(self.q_table, f, indent=4)
        except Exception as e:
            print(f"[RL Agent]: Error saving Q-table: {e}")

    def _get_q_values(self, state):
        if state not in self.q_table:
            self.q_table[state] = {}
        return self.q_table[state]

    def choose_action(self, state, available_actions):
        if not available_actions:
            return None
        
        # Epsilon-greedy exploration
        if random.random() < self.epsilon:
            action = random.choice(available_actions)
            print(f"[RL Agent]: Explored action '{action}' for state '{state}'")
            return action
        
        # Exploitation
        q_vals = self._get_q_values(state)
        # Ensure all available actions have a default Q-value (0.0)
        for act in available_actions:
            if act not in q_vals:
                q_vals[act] = 0.0
        
        # Find best action
        best_actions = []
        max_val = -float('inf')
        for act in available_actions:
            val = q_vals.get(act, 0.0)
            if val > max_val:
                max_val = val
                best_actions = [act]
            elif val == max_val:
                best_actions.append(act)
        
        action = random.choice(best_actions)
        print(f"[RL Agent]: Exploited best action '{action}' for state '{state}' (Q-value: {max_val:.2f})")
        return action

    def update_q_value(self, state, action, reward):
        q_vals = self._get_q_values(state)
        old_val = q_vals.get(action, 0.0)
        # Q-learning update: Q(s,a) = Q(s,a) + alpha * (reward - Q(s,a))
        new_val = old_val + self.alpha * (reward - old_val)
        q_vals[action] = new_val
        self.save_q_table()
        print(f"[RL Agent]: Learned! Updated Q(state='{state}', action='{action}'): {old_val:.2f} -> {new_val:.2f} (Reward: {reward})")
