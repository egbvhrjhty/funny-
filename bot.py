import os
# GitHub सर्वर पर स्क्रीन नहीं होती, इसलिए Pygame को Dummy Mode में चलाना जरूरी है
os.environ["SDL_VIDEODRIVER"] = "dummy"

import pygame
import math
import numpy as np
import asyncio
import random
import cv2
import wave
import struct
import re
from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_audioclips, CompositeAudioClip
import moviepy.audio.fx.all as afx
import edge_tts

# ==========================================
# SETTINGS & FOLDERS
# ==========================================
OUTPUT_FOLDER = "./output"
TEMP_FOLDER = "./temp"
TEXT_FILE_PATH = "./jokes.txt"
FONT_PATH = "./NirmalaB.ttf" # यह फाइल गिटहब पर होनी चाहिए

os.makedirs(OUTPUT_FOLDER, exist_ok=True)
os.makedirs(TEMP_FOLDER, exist_ok=True)

WIDTH, HEIGHT = 720, 1280
FPS = 30

char_colors = {
    "Wife": (255, 105, 180),
    "Husband": (100, 200, 100)
}

# ==========================================
# AUDIO GENERATION
# ==========================================
def generate_sfx(filename, effect_type):
    sample_rate = 44100
    duration = 0.6 if effect_type in ["shock", "angry"] else 0.8
    obj = wave.open(filename, 'w')
    obj.setnchannels(1)
    obj.setsampwidth(2)
    obj.setframerate(sample_rate)
    
    for i in range(int(sample_rate * duration)):
        if effect_type == "shock": freq = 300 + (i / sample_rate) * 1500
        elif effect_type == "sad": freq = 600 - (i / sample_rate) * 400
        elif effect_type == "angry": freq = 300 + 150 * math.sin(2.0 * math.pi * 15 * (i / sample_rate))
        else: freq = 400
            
        value = int(32767.0 * 0.5 * math.sin(2.0 * math.pi * freq * (i / sample_rate)))
        obj.writeframesraw(struct.pack('<h', value))
    obj.close()

async def download_voices(story_lines):
    print("🎙️ Generating AI Voices & Sound Effects...")
    for i, line in enumerate(story_lines):
        filename = os.path.join(TEMP_FOLDER, f"temp_audio_{i}.mp3")
        line["audio"] = filename
        communicate = edge_tts.Communicate(line["text"], line["voice"], rate=line["rate"])
        await communicate.save(filename)
        
        if "emotion" in line and line["emotion"] in ["shock", "sad", "angry"]:
            sfx_file = os.path.join(TEMP_FOLDER, f"sfx_{i}.wav")
            generate_sfx(sfx_file, line["emotion"])
            line["sfx"] = sfx_file

# ==========================================
# TEXT PARSING
# ==========================================
def fetch_and_delete_first_joke():
    if not os.path.exists(TEXT_FILE_PATH):
        print("❌ jokes.txt फाइल नहीं मिली!")
        return None
    with open(TEXT_FILE_PATH, 'r', encoding='utf-8') as f:
        content = f.read()
        
    jokes = [s.strip() for s in content.split("=====") if s.strip()]
    if not jokes:
        print("❌ कोई जोक/कहानी नहीं बची है!")
        return None
        
    first_joke = jokes[0]
    remaining_jokes = jokes[1:]
    
    with open(TEXT_FILE_PATH, 'w', encoding='utf-8') as f:
        f.write("\n=====\n".join(remaining_jokes))
        
    # Parse Joke Text into Dictionary
    story_data = []
    lines = first_joke.split('\n')
    for idx, line in enumerate(lines):
        line = line.strip()
        if not line: continue
        
        match = re.match(r'^(.*?)(?:\s*\((.*?)\))?\s*:\s*(.*)$', line)
        if match:
            speaker = match.group(1).strip()
            emotion = match.group(2).strip().lower() if match.group(2) else "normal"
            text = match.group(3).strip()
            
            voice = "hi-IN-SwaraNeural" if speaker.lower() == "wife" else "hi-IN-MadhurNeural"
            story_data.append({
                "scene": idx + 1,
                "speaker": "Wife" if speaker.lower() == "wife" else "Husband",
                "text": text,
                "voice": voice,
                "emotion": emotion,
                "rate": "+10%"
            })
    return story_data

# ==========================================
# DRAWING FUNCTIONS
# ==========================================
def draw_cartoon_background(surf, timer):
    surf.fill((160, 140, 240)) 
    pygame.draw.rect(surf, (200, 140, 100), (0, HEIGHT - 350, WIDTH, 350))
    pygame.draw.ellipse(surf, (255, 150, 180), (WIDTH//2 - 250, HEIGHT - 280, 500, 120))
    
    window_x, window_y = WIDTH//2 - 150, 150
    pygame.draw.rect(surf, (20, 20, 60), (window_x, window_y, 300, 250))
    pygame.draw.circle(surf, (255, 255, 200), (window_x + 220, window_y + 70), 40)
    pygame.draw.rect(surf, (255, 255, 255), (window_x, window_y, 300, 250), 12) 
    pygame.draw.line(surf, (255, 255, 255), (window_x + 150, window_y), (window_x + 150, window_y + 250), 10)
    pygame.draw.line(surf, (255, 255, 255), (window_x, window_y + 125), (window_x + 300, window_y + 125), 10)

class Character:
    def __init__(self, name, color):
        self.name = name
        self.color = color
        self.pos = np.array([0.0, 0.0])
        self.target_pos = np.array([0.0, 0.0])
        self.blink_timer = 0
        self.is_blinking = False
        self.flip = False

    def update(self):
        self.pos += (self.target_pos - self.pos) * 0.1
        self.blink_timer += 1
        if self.blink_timer > random.randint(80, 150):
            self.is_blinking = True
            if self.blink_timer > 160:
                self.is_blinking = False
                self.blink_timer = 0

    def draw(self, surf, is_talking, emotion, timer):
        x, y = int(self.pos[0]), int(self.pos[1])
        body_y = y 
        arm_swing = math.sin(timer * 0.5) * 20 if is_talking else 0
        
        pygame.draw.ellipse(surf, (0,0,0,80), (x-70, y+180, 140, 30))
        pygame.draw.line(surf, (20,20,20), (x - 30, body_y + 160), (x - 30, y + 190), 12)
        pygame.draw.line(surf, (20,20,20), (x + 30, body_y + 160), (x + 30, y + 190), 12)
        pygame.draw.rect(surf, self.color, (x-60, body_y, 120, 160), border_radius=30)
        pygame.draw.rect(surf, (20,20,20), (x-60, body_y, 120, 160), 6, border_radius=30)

        pygame.draw.line(surf, (20,20,20), (x - 60, body_y + 50), (x - 90, body_y + 90 + arm_swing), 12)
        pygame.draw.line(surf, (20,20,20), (x + 60, body_y + 50), (x + 90, body_y + 90 - arm_swing), 12)

        head_bounce = math.sin(timer * 1.5) * 5 if is_talking else 0
        head_y = body_y - 60 + head_bounce
        pygame.draw.circle(surf, (255, 220, 180), (x, head_y), 70)
        pygame.draw.circle(surf, (20,20,20), (x, head_y), 70, 6)

        eye_w, eye_h = 20, (4 if self.is_blinking or emotion == "sleep" else 30)
        look_offset = -10 if self.flip else 10
        if emotion == "shock": eye_h = 50
        
        pygame.draw.ellipse(surf, (20,20,20), (x - 30 + look_offset, head_y - 20, eye_w, eye_h))
        pygame.draw.ellipse(surf, (20,20,20), (x + 10 + look_offset, head_y - 20, eye_w, eye_h))
        
        if emotion == "angry":
            pygame.draw.line(surf, (20,20,20), (x - 40 + look_offset, head_y - 35), (x - 15 + look_offset, head_y - 15), 5)
            pygame.draw.line(surf, (20,20,20), (x + 35 + look_offset, head_y - 35), (x + 10 + look_offset, head_y - 15), 5)

        if is_talking:
            m_size = abs(math.sin(timer * 1.5)) * 30 + 5
            if emotion == "shock": m_size = 40
            if emotion == "angry": m_size = 35
            pygame.draw.ellipse(surf, (180, 0, 0), (x - 20 + look_offset, head_y + 25, 40, m_size))
        else:
            if emotion == "angry":
                pygame.draw.line(surf, (20,20,20), (x - 15 + look_offset, head_y + 40), (x + 15 + look_offset, head_y + 30), 6)
            else:
                pygame.draw.line(surf, (20,20,20), (x - 15 + look_offset, head_y + 35), (x + 15 + look_offset, head_y + 35), 6)

def render_multiline_text(surf, text, font, color, x, y, max_width):
    words = text.split(" ")
    lines, current_line = [], ""
    for word in words:
        test_line = current_line + word + " "
        if font.size(test_line)[0] < max_width:
            current_line = test_line
        else:
            lines.append(current_line)
            current_line = word + " "
    lines.append(current_line)
    for i, line in enumerate(lines):
        txt_surf = font.render(line, True, color)
        surf.blit(txt_surf, (x, y + i * 45))

# ==========================================
# MAIN EXECUTION
# ==========================================
async def main():
    print("🚀 Auto Video Generator Started...")
    
    current_story = fetch_and_delete_first_joke()
    if not current_story:
        return
        
    await download_voices(current_story)

    pygame.init()
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    
    try: hindi_font = pygame.font.Font(FONT_PATH, 40)
    except: hindi_font = pygame.font.SysFont("Arial", 40)

    temp_video_path = os.path.join(TEMP_FOLDER, "temp_video.mp4")
    final_video_path = os.path.join(OUTPUT_FOLDER, "FINAL_UPLOAD.mp4")

    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    video_writer = cv2.VideoWriter(temp_video_path, fourcc, FPS, (WIDTH, HEIGHT))

    chars = {speaker: Character(speaker, color) for speaker, color in char_colors.items()}
    audio_clips = []
    timer = 0

    print("🎥 Rendering Video Frames...")
    for idx, line in enumerate(current_story):
        speaker = line["speaker"]
        emotion = line.get("emotion", "normal")
        
        speech_clip = AudioFileClip(line["audio"]).fx(afx.volumex, 1.8)
        
        if "sfx" in line:
            sfx_clip = AudioFileClip(line["sfx"]).fx(afx.volumex, 1.5)
            mixed_audio = CompositeAudioClip([speech_clip.set_start(0), sfx_clip.set_start(0)])
            audio_clips.append(mixed_audio)
        else:
            audio_clips.append(speech_clip)
        
        frames_to_render = int(speech_clip.duration * FPS) + 5 # 5 extra frames for pause
        
        # Position Logic
        if "Wife" in chars:
            chars["Wife"].target_pos = [WIDTH//2 - 180, HEIGHT//2 + 100]
            chars["Wife"].flip = False
        if "Husband" in chars:
            chars["Husband"].target_pos = [WIDTH//2 + 180, HEIGHT//2 + 100]
            chars["Husband"].flip = True   

        for f in range(frames_to_render):
            timer += 1
            draw_cartoon_background(screen, timer)
                
            for name, char in chars.items():
                is_talking = (name == speaker and f < int(speech_clip.duration * FPS))
                char.update()
                char.draw(screen, is_talking, emotion if is_talking else "normal", timer)
                
            sub_rect = pygame.Rect(40, HEIGHT - 250, WIDTH - 80, 180)
            pygame.draw.rect(screen, (0, 0, 0, 200), sub_rect, border_radius=25)
            speaker_txt = hindi_font.render(f"{speaker}:", True, (255, 0, 0) if emotion == "angry" else (255, 255, 0))
            screen.blit(speaker_txt, (sub_rect.x + 30, sub_rect.y + 20))
            render_multiline_text(screen, line['text'], hindi_font, (255, 255, 255), sub_rect.x + 30, sub_rect.y + 70, sub_rect.width - 60)

            pygame.display.flip()
            
            view = pygame.surfarray.array3d(screen)
            view = view.transpose([1, 0, 2])
            img_bgr = cv2.cvtColor(view, cv2.COLOR_RGB2BGR)
            video_writer.write(img_bgr)

    video_writer.release()
    pygame.quit()

    print("🎧 Merging Audio and Video...")
    final_audio = concatenate_audioclips(audio_clips)
    video_clip = VideoFileClip(temp_video_path)
    final_video = video_clip.set_audio(final_audio)

    final_video.write_videofile(final_video_path, codec="libx264", audio_codec="aac", fps=FPS, preset="ultrafast", logger=None)
    video_clip.close()
    
    print(f"✅ Video successfully saved at: {final_video_path}")

if __name__ == "__main__":
    asyncio.run(main())
