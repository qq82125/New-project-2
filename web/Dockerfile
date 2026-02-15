FROM node:22-alpine

WORKDIR /app

COPY package.json /app/package.json
COPY tsconfig.json /app/tsconfig.json
COPY next.config.ts /app/next.config.ts
COPY next-env.d.ts /app/next-env.d.ts
RUN npm install

COPY . /app

RUN npm run build

CMD ["npm", "run", "start"]
