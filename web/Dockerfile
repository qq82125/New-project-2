FROM node:22-alpine

WORKDIR /app

COPY web/package.json /app/package.json
COPY web/tsconfig.json /app/tsconfig.json
COPY web/next.config.ts /app/next.config.ts
COPY web/next-env.d.ts /app/next-env.d.ts
RUN npm install

COPY web /app

RUN npm run build

CMD ["npm", "run", "start"]
