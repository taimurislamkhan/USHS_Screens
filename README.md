# USHS Screens - Electron Application

A modular Electron application for USHS screen interfaces.

## Project Structure

```
USHS_Screens/
├── assets/           # Images and SVG icons
├── admin/            # Admin interface screens
├── settings/         # Settings interface screens
├── main.js           # Electron main process
├── preload.js        # Electron preload script
├── index.html        # Main HTML entry point
├── HomeScreen.html   # Home screen component
└── start_app.sh      # Convenience launcher
```

## Quick Start

To run the application:

```bash
./start_app.sh
```

Or directly with npm:

```bash
npm start
```

## Dependencies

- Node.js and npm (for Electron)

## Configuration

- UI configuration is stored in `config.json`
- Tip states and other data are tracked in `tip_states.json`