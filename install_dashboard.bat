IF EXIST dashboard (
  RMDIR /S /Q dashboard
)
npx -y create-vite@latest dashboard --template react-ts
cd dashboard
call npm install
call npm install tailwindcss postcss autoprefixer recharts lucide-react clsx tailwind-merge
call npx tailwindcss init -p
