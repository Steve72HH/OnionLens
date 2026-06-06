FROM node:22-alpine

WORKDIR /app
COPY package*.json .
RUN npm ci --omit=dev --ignore-scripts
COPY server.js .
COPY public ./public

CMD ["node", "server.js"]
