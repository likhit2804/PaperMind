# Use a lightweight base image with Node.js and Python pre-installed
FROM nikolaik/python-nodejs:python3.11-nodejs20-slim

WORKDIR /app

# Copy dependency files
COPY requirements.txt ./
COPY backend-node/package*.json ./backend-node/
COPY frontend-react/package*.json ./frontend-react/

# Install Node.js dependencies
RUN cd frontend-react && npm ci
RUN cd backend-node && npm ci

# Install Python requirements
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application
COPY . .

# Build the React frontend into static assets (placed in frontend-react/dist)
RUN cd frontend-react && npm run build

# Set production envs
ENV NODE_ENV=production
ENV PORT=8000

EXPOSE 8000

# Start backend node which hosts both the API and the React files
CMD ["npm", "--prefix", "backend-node", "start"]
