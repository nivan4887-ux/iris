# Building the Aura 2.0 Android APK

## Quick start — test on phone RIGHT NOW (no build needed)

1. Install Expo Go on your Android phone from the Play Store
2. On your PC, run:
   ```
   cd "aura-mobile"
   npx expo start
   ```
3. Scan the QR code in Expo Go — the app opens instantly

## Set the backend IP

Your phone needs to reach the PC running the backend.

1. On PC: open Command Prompt → type `ipconfig` → note the IPv4 Address (e.g. 192.168.1.42)
2. Make sure phone and PC are on the **same Wi-Fi**
3. Open the app → tap ⚙ Settings → set URL to `http://192.168.1.42:8000`
4. Tap Test Connection to verify

## Build a real APK (installable file)

### Option A — EAS Build (easiest, free tier, no Android SDK needed)

```bash
npm install -g eas-cli
eas login           # create free account at expo.dev if needed
eas build --platform android --profile preview
```

- Takes ~10-15 minutes
- Downloads the APK link when done
- Install on any Android phone

### Option B — Local build (needs Android Studio)

```bash
npx expo run:android   # requires Android SDK installed
```

## Assets needed before building APK

Create these images in the `assets/` folder:
- `icon.png` — 1024×1024 px app icon
- `splash.png` — 1284×2778 px splash screen
- `adaptive-icon.png` — 1024×1024 px (for Android adaptive icon)

Simplest option: copy any square PNG and rename it to each.
The app will work without custom icons (Expo uses defaults).

## Backend must be running

```
cd "Aura Backend"
python run.py
```

Keep it running while the app is open. For production, deploy the
backend to a cloud server (Render, Railway, etc.) and update the API URL.
