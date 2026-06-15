# 🍃 MongoDB Setup & Connection Guide (HERALD Project)

This guide provides step-by-step instructions on how to install, run, and connect MongoDB to your HERALD project.

---

## 🛠️ Method 1: Local Installation (Kali Linux / Debian / Ubuntu)

Since Kali Linux is based on Debian, we will use the official MongoDB Debian repository.

### Step 1: Install Required Dependencies
Open your terminal and run:
```bash
sudo apt update
sudo apt install -y gnupg curl
```

### Step 2: Import MongoDB GPG Key
Download and import the public key for verifying MongoDB packages:
```bash
curl -fsSL https://pgp.mongodb.com/server-7.0.asc | sudo gpg -o /usr/share/keyrings/mongodb-server-7.0.gpg --dearmor
```

### Step 3: Add MongoDB Repository (With SHA-1 Bypass)
Since early 2026, Debian/Kali rejects MongoDB's GPG keys because they contain deprecated SHA-1 signatures. To bypass this security policy check for this specific repository, add the `trusted=yes` flag:
```bash
echo "deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg trusted=yes ] https://repo.mongodb.org/apt/debian bookworm/mongodb-org/7.0 main" | sudo tee /etc/apt/sources.list.d/mongodb-org-7.0.list
```

### Step 4: Install MongoDB
Update your packages and install MongoDB:
```bash
sudo apt update
sudo apt install -y mongodb-org
```

### Step 5: Start & Enable MongoDB Service
Start the service and make it run on system startup:
```bash
sudo systemctl daemon-reload
sudo systemctl start mongod
sudo systemctl enable mongod
```

### Step 6: Verify Service is Running
Check the status to ensure it says `active (running)`:
```bash
sudo systemctl status mongod
```

---

## 🐳 Method 2: Docker Installation (Recommended & Super Easy)

If you have Docker installed, this is the fastest way to get MongoDB running without modifying system repositories.

### Step 1: Run MongoDB Container
Run the official MongoDB container in the background:
```bash
docker run -d --name mongodb-local -p 27017:27017 -v mongo_data:/data/db mongo:latest
```

### Step 2: Check Container Status
Verify it's running:
```bash
docker ps
```

---

## 🔌 Connecting HERALD to MongoDB

### Step 1: Environment Configuration
Make sure your `.env` file contains the correct connection URL. Open your `.env` and verify this line:
```env
MONGO_URL=mongodb://localhost:27017/
```

### Step 2: Install Python Driver
Ensure the MongoDB driver is installed in your python environment:
```bash
pip install pymongo
```

### Step 3: Verify HERALD logs
Run HERALD to see if it automatically connects:
```bash
python3 main.py
```
If successful, you will see this log:
```
[Memory]: MongoDB connected
```

---

## ⚡ Roman Urdu Summary / Jaldi Setup Steps:

1. Agar aapke paas **Docker** install hai, to ye command chalayein:
   ```bash
   docker run -d --name mongodb-local -p 27017:27017 -v mongo_data:/data/db mongo:latest
   ```
2. Agar local system par install karna hai:
   - **GPG Key add karein:**
     `curl -fsSL https://pgp.mongodb.com/server-7.0.asc | sudo gpg -o /usr/share/keyrings/mongodb-server-7.0.gpg --dearmor`
   - **Repo add karein (GPG SHA-1 signature bypass ke saath):**
     `echo "deb [ arch=amd64,arm64 signed-by=/usr/share/keyrings/mongodb-server-7.0.gpg trusted=yes ] https://repo.mongodb.org/apt/debian bookworm/mongodb-org/7.0 main" | sudo tee /etc/apt/sources.list.d/mongodb-org-7.0.list`
   - **Install aur start karein:**
     `sudo apt update && sudo apt install -y mongodb-org && sudo systemctl start mongod`
3. Apne `.env` file mein check karein ke `MONGO_URL=mongodb://localhost:27017/` set ho.
4. Python environment mein `pip install pymongo` run karein.
5. Jab aap `python3 main.py` run karenge, console par print hoga: `[Memory]: MongoDB connected` aur saari history & logs database mein save hona shuru ho jayengi!

---

> [!NOTE]
> We optimized `agent/memory.py` to do a **fast socket check (100ms)** before attempting to connect to MongoDB. Now, if MongoDB is offline, the program will skip connection attempts instantly and will **not** freeze or cause any delays!
