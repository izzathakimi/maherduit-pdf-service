#!/usr/bin/env python3
"""
Task Completion Sound Generator
Creates a pleasant completion sound when Claude finishes tasks
"""
import wave
import math
import struct
import sys
import os

def generate_completion_sound(filename="task_complete.wav", duration=1.0):
    """Generate a pleasant completion sound"""
    sample_rate = 44100
    num_samples = int(sample_rate * duration)
    
    # Create a pleasant two-tone completion sound
    samples = []
    
    for i in range(num_samples):
        t = i / sample_rate
        
        # First tone (higher pitch) - first half
        if t < duration * 0.3:
            freq1 = 800  # High note
            volume = 0.3 * math.sin(math.pi * t / (duration * 0.3))  # Fade in
        # Second tone (lower pitch) - second half  
        elif t < duration * 0.6:
            freq1 = 600  # Medium note
            volume = 0.3
        else:
            freq1 = 400  # Low note  
            volume = 0.3 * math.sin(math.pi * (duration - t) / (duration * 0.4))  # Fade out
        
        # Generate sine wave
        sample = volume * math.sin(2 * math.pi * freq1 * t)
        
        # Convert to 16-bit integer
        sample_int = int(sample * 32767)
        samples.append(sample_int)
    
    # Write WAV file
    with wave.open(filename, 'w') as wav_file:
        wav_file.setnchannels(1)  # Mono
        wav_file.setsampwidth(2)  # 16-bit
        wav_file.setframerate(sample_rate)
        
        # Pack samples as binary data
        packed_samples = struct.pack('<' + 'h' * len(samples), *samples)
        wav_file.writeframes(packed_samples)
    
    print(f"✅ Generated completion sound: {filename}")
    return filename

def play_sound(filename="task_complete.wav"):
    """Play the completion sound using available system tools"""
    
    if not os.path.exists(filename):
        print(f"❌ Sound file {filename} not found. Generating...")
        generate_completion_sound(filename)
    
    # Try different audio players
    players = [
        f"aplay {filename}",           # Linux ALSA
        f"paplay {filename}",          # Linux PulseAudio  
        f"afplay {filename}",          # macOS
        f"powershell -c (New-Object Media.SoundPlayer '{filename}').PlaySync()",  # Windows
        f"ffplay -nodisp -autoexit {filename}",  # FFmpeg
        f"mpg123 {filename}",          # mpg123
        f"cvlc --play-and-exit {filename}"  # VLC
    ]
    
    played = False
    for player_cmd in players:
        try:
            result = os.system(f"{player_cmd} 2>/dev/null")
            if result == 0:
                print(f"🔊 Played completion sound using: {player_cmd.split()[0]}")
                played = True
                break
        except:
            continue
    
    if not played:
        print("🔇 No audio player found, but sound file created!")
        print(f"   You can manually play: {filename}")
    
    return played

def main():
    """Main function"""
    if len(sys.argv) > 1:
        if sys.argv[1] == "generate":
            generate_completion_sound()
        elif sys.argv[1] == "play":
            play_sound()
        else:
            print("Usage: python3 task_complete_sound.py [generate|play]")
    else:
        # Default: generate and play
        generate_completion_sound()
        play_sound()

if __name__ == "__main__":
    main()