# Ejnar frontend — Next.js standalone-build i slank runtime-image.
#
#   docker build --build-arg BACKEND_URL=http://backend:8000 -t ejnar-web .
#   docker run -p 3000:3000 ejnar-web
#
# NB: BACKEND_URL skal gives ved BYGGETID — next.config.ts' rewrites bages ind
# i buildet. Ved deploy uden Docker (Vercel) sættes den som projekt-env, som
# også er tilgængelig under build.
FROM node:22-alpine AS build
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
ARG BACKEND_URL=http://backend:8000
ENV BACKEND_URL=$BACKEND_URL
RUN npm run build

FROM node:22-alpine
WORKDIR /app
ENV NODE_ENV=production \
    HOSTNAME=0.0.0.0 \
    PORT=3000 \
    NEXT_TELEMETRY_DISABLED=1
COPY --from=build /app/.next/standalone ./
COPY --from=build /app/.next/static ./.next/static
COPY --from=build /app/public ./public
EXPOSE 3000
CMD ["node", "server.js"]
