node -v
v22.12.0

npm -v
10.9.0

# new project
npm create vite@latest flood-viz -- --template vue-ts
cd flood-viz


npm i vue-router pinia axios leaflet chart.js vue-chartjs


npm i -D tailwindcss postcss autoprefixer
npx tailwindcss init -p

# development 
npm run dev

# build
npm run build