FROM node:22-alpine

WORKDIR /app

COPY package.json /app/package.json
COPY package-lock.json /app/package-lock.json
COPY tsconfig.json /app/tsconfig.json
COPY next.config.ts /app/next.config.ts
COPY next-env.d.ts /app/next-env.d.ts

RUN npm ci

# Copy only source directories used by Next.js build.
COPY app /app/app
COPY components /app/components
COPY constants /app/constants
COPY lib /app/lib

RUN npm run build

CMD ["npm", "run", "start"]
