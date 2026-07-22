# Xeno AI Desktop Application

God-tier desktop UI for Xeno AI Agent System built with Next.js 14 and Electron 28.

## Features

- 🎨 **Modern Dark Theme** - Glass morphism, gradient effects, neon accents
- 💬 **Rich Chat Interface** - Markdown support, code highlighting, file attachments
- 📊 **Real-time Dashboard** - Live metrics, agent status, task tracking
- 🎤 **Voice Control** - Push-to-talk and always-listening modes
- 📁 **Task Manager** - Kanban boards, Gantt charts, dependency graphs
- 🧠 **Memory Explorer** - Visualize knowledge graphs and memory tiers
- 🔌 **Electron Integration** - Native desktop app with system tray

## Tech Stack

- **Frontend**: Next.js 14, React 18, TypeScript
- **Styling**: Tailwind CSS, Radix UI, Framer Motion
- **Charts**: Recharts
- **Code Editor**: Monaco Editor
- **Desktop**: Electron 28
- **State**: Zustand
- **Real-time**: Socket.IO

## Getting Started

### Prerequisites

- Node.js 18+
- Python 3.11+ (for backend)
- uv package manager

### Installation

```bash
# Install frontend dependencies
cd frontend
npm install

# Install backend dependencies (from project root)
cd ..
uv sync
```

### Development

```bash
# Run in development mode (Next.js dev server)
npm run dev

# Or run with Electron
npm run electron:dev
```

### Build

```bash
# Build for production
npm run build

# Build Electron app
npm run electron:build
```

## Project Structure

```
frontend/
├── electron/          # Electron main process
│   ├── main.js       # Main entry point
│   └── preload.js    # Preload script
├── src/
│   ├── app/          # Next.js app router
│   ├── components/   # React components
│   │   ├── Chat/
│   │   ├── Dashboard/
│   │   ├── Sidebar/
│   │   └── ...
│   ├── hooks/        # Custom hooks
│   ├── lib/          # Utilities
│   ├── store/        # Zustand stores
│   └── types/        # TypeScript types
├── public/           # Static assets
└── package.json
```

## Configuration

Create a `.env.local` file:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
NEXT_PUBLIC_WS_URL=ws://localhost:8000
```

## Available Scripts

- `npm run dev` - Start Next.js dev server
- `npm run build` - Build for production
- `npm run start` - Start production server
- `npm run lint` - Run ESLint
- `npm run electron:dev` - Run with Electron in dev mode
- `npm run electron:build` - Build Electron app
- `npm run electron:start` - Start built Electron app

## License

MIT
