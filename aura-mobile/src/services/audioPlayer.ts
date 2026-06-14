import { Audio } from 'expo-av';
import * as FileSystem from 'expo-file-system';
import * as Speech from 'expo-speech';

type QueueItem = { base64: string; priority: number };

class AudioPlayer {
  private queue: QueueItem[] = [];
  private playing = false;
  private currentSound: Audio.Sound | null = null;
  private speakingTTS = false;

  async init() {
    await Audio.setAudioModeAsync({
      allowsRecordingIOS: false,
      playsInSilentModeIOS: true,
      shouldDuckAndroid: true,
      playThroughEarpieceAndroid: false,
    });
  }

  enqueue(base64: string, priority: number) {
    if (priority === 1) {
      this.interrupt();
      this.queue.unshift({ base64, priority });
    } else {
      this.queue.push({ base64, priority });
    }
    this._next();
  }

  speak(text: string, priority: number) {
    if (priority === 1) {
      this.interrupt();
      this._doSpeak(text);
    } else if (!this.playing && !this.speakingTTS) {
      this._doSpeak(text);
    }
  }

  interrupt() {
    this.queue = [];
    if (this.currentSound) {
      this.currentSound.stopAsync().catch(() => {});
      this.currentSound.unloadAsync().catch(() => {});
      this.currentSound = null;
    }
    Speech.stop();
    this.playing = false;
    this.speakingTTS = false;
  }

  private _doSpeak(text: string) {
    this.speakingTTS = true;
    Speech.speak(text, {
      language: 'en-US',
      rate: 0.9,
      pitch: 1.0,
      onDone: () => {
        this.speakingTTS = false;
        this._next();
      },
      onError: () => {
        this.speakingTTS = false;
        this._next();
      },
      onStopped: () => {
        this.speakingTTS = false;
      },
    });
  }

  private async _next() {
    if (this.playing || this.speakingTTS || this.queue.length === 0) return;
    const item = this.queue.shift()!;
    this.playing = true;

    try {
      const uri = `${FileSystem.cacheDirectory}aura_audio_${Date.now()}.mp3`;
      await FileSystem.writeAsStringAsync(uri, item.base64, {
        encoding: FileSystem.EncodingType.Base64,
      });

      const { sound } = await Audio.Sound.createAsync(
        { uri },
        { shouldPlay: true, volume: 1.0 },
      );
      this.currentSound = sound;

      sound.setOnPlaybackStatusUpdate((status) => {
        if (!status.isLoaded) return;
        if (status.didJustFinish) {
          sound.unloadAsync().catch(() => {});
          FileSystem.deleteAsync(uri, { idempotent: true }).catch(() => {});
          this.currentSound = null;
          this.playing = false;
          this._next();
        }
      });
    } catch {
      this.playing = false;
      this._next();
    }
  }
}

export const audioPlayer = new AudioPlayer();
