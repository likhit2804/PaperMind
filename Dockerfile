# Use a lightweight base image with Node.js and Python pre-installed
FROM nikolaik/python-nodejs:python3.11-nodejs20-slim

WORKDIR /app

# Copy dependency files
COPY requirements.txt ./
COPY backend-node/package*.json ./backend-node/

# Install Node.js backend dependencies
RUN cd backend-node && npm ci

# Install Python requirements for research extraction pipeline
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Set production envs
ENV NODE_ENV=production
ENV PORT=8000

EXPOSE 8000

# Start pure Node.js backend API
CMD ["npm", "--prefix", "backend-node", "start"]
