import os
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
FONT_PATH = "./NirmalaB.ttf" 
BG_FOLDER = "./bgs" 
BGM_FILE = "./bgm.mp3"     # हल्का बैकग्राउंड म्यूजिक
LAUGH_FILE = "./laugh.mp3" # जोक के अंत में बजने वाली हंसी

os.makedirs(OUTPUT_FOLDER, exist_ok=True)
os.makedirs(TEMP_FOLDER, exist_ok=True)
os.makedirs(BG_FOLDER, exist_ok=True)

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
    duration = 0.6
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
    print("🎙️ Generating Funny Cartoon Voices...")
    for i, line in enumerate(story_lines):
        filename = os.path.join(TEMP_FOLDER, f"temp_audio_{i}.mp3")
        line["audio"] = filename
        
        # 🟢 नया: Pitch (पिच) और Rate (स्पीड) को पास किया जा रहा है
        communicate = edge_tts.Communicate(line["text"], line["voice"], rate=line["rate"], pitch=line["pitch"])
        await communicate.save(filename)
        
        if "emotion" in line and line["emotion"] in ["shock", "sad", "angry"]:
            sfx_file = os.path.join(TEMP_FOLDER, f"sfx_{i}.wav")
            generate_sfx(sfx_file, line["emotion"])
            line["sfx"] = sfx_file

# ==========================================
# TEXT PARSING (WITH FUNNY VOICE TUNING)
# ==========================================
def fetch_and_delete_first_joke():
    if not os.path.exists(TEXT_FILE_PATH):
        return None
    with open(TEXT_FILE_PATH, 'r', encoding='utf-8') as f:
        content = f.read()
        
    jokes = [s.strip() for s in content.split("=====") if s.strip()]
    if not jokes:
        return None
        
    first_joke = jokes[0]
    remaining_jokes = jokes[1:]
    
    with open(TEXT_FILE_PATH, 'w', encoding='utf-8') as f:
        f.write("\n=====\n".join(remaining_jokes))
        
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
            
            # 🟢 नया: फनी कार्टून आवाज़ के लिए Settings (तेज़ स्पीड और पतली आवाज़)
            is_wife = (speaker.lower() == "wife")
            voice = "hi-IN-SwaraNeural" if is_wife else "hi-IN-MadhurNeural"
            
            # पतली और मज़ेदार आवाज़ के लिए
            pitch = "+45Hz" if is_wife else "+35Hz" 
            rate = "+25%" if is_wife else "+20%"
            
            story_data.append({
                "scene": idx + 1,
                "speaker": "Wife" if is_wife else "Husband",
                "text": text,
                "voice": voice,
                "emotion": emotion,
                "pitch": pitch,
                "rate": rate
            })
    return story_data

# ==========================================
# DRAWING FUNCTIONS
# ==========================================
def draw_background(surf, bg_img):
    if bg_img: surf.blit(bg_img, (0, 0))
    else: surf.fill((160, 140, 240)) 

def render_text_with_outline(surf, text, font, color, x, y, outline_color=(0,0,0), thickness=3):
    words = text.split(" ")
    lines, current_line = [], ""
    max_width = WIDTH - 60
    
    for word in words:
        test_line = current_line + word + " "
        if font.size(test_line)[0] < max_width:
            current_line = test_line
        else:
            lines.append(current_line)
            current_line = word + " "
    lines.append(current_line)
    
    for i, line in enumerate(lines):
        for dx in range(-thickness, thickness + 1):
            for dy in range(-thickness, thickness + 1):
                if dx != 0 or dy != 0:
                    txt_bg = font.render(line, True, outline_color)
                    surf.blit(txt_bg, (x + dx, y + i * 50 + dy))
        txt_fg = font.render(line, True, color)
        surf.blit(txt_fg, (x, y + i * 50))

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
        
        if emotion == "shock" and is_talking:
            y -= abs(math.sin(timer * 0.8)) * 40 
            
        body_y = y 
        arm_swing = math.sin(timer * 0.5) * 20 if is_talking else 0
        
        pygame.draw.ellipse(surf, (0,0,0,80), (x-70, self.pos[1]+180, 140, 30))
        pygame.draw.line(surf, (20,20,20), (x - 30, body_y + 160), (x - 30, self.pos[1] + 190), 12)
        pygame.draw.line(surf, (20,20,20), (x + 30, body_y + 160), (x + 30, self.pos[1] + 190), 12)
        pygame.draw.rect(surf, self.color, (x-60, body_y, 120, 160), border_radius=30)
        pygame.draw.rect(surf, (20,20,20), (x-60, body_y, 120, 160), 6, border_radius=30)

        if emotion == "angry" and is_talking: arm_swing = math.sin(timer * 2.0) * 40
        pygame.draw.line(surf, (20,20,20), (x - 60, body_y + 50), (x - 90, body_y + 90 + arm_swing), 12)
        pygame.draw.line(surf, (20,20,20), (x + 60, body_y + 50), (x + 90, body_y + 90 - arm_swing), 12)

        head_bounce = math.sin(timer * 1.5) * 5 if is_talking else 0
        head_y = body_y - 60 + head_bounce
        
        face_color = (255, 120, 120) if emotion == "angry" else (255, 220, 180)
        pygame.draw.circle(surf, face_color, (x, head_y), 70)
        pygame.draw.circle(surf, (20,20,20), (x, head_y), 70, 6)

        eye_w, eye_h = 20, (4 if self.is_blinking else 30)
        look_offset = -10 if self.flip else 10
        if emotion == "shock": eye_h = 50
        
        pygame.draw.ellipse(surf, (20,20,20), (x - 30 + look_offset, head_y - 20, eye_w, eye_h))
        pygame.draw.ellipse(surf, (20,20,20), (x + 10 + look_offset, head_y - 20, eye_w, eye_h))
        
        if emotion == "angry":
            pygame.draw.line(surf, (20,20,20), (x - 40 + look_offset, head_y - 35), (x - 15 + look_offset, head_y - 15), 5)
            pygame.draw.line(surf, (20,20,20), (x + 35 + look_offset, head_y - 35), (x + 10 + look_offset, head_y - 15), 5)
            pygame.draw.line(surf, (200,0,0), (x + 20, head_y - 50), (x + 40, head_y - 30), 4)
            pygame.draw.line(surf, (200,0,0), (x + 40, head_y - 50), (x + 20, head_y - 30), 4)

        if emotion == "sad":
            pygame.draw.ellipse(surf, (0, 191, 255), (x + 30 + look_offset, head_y - 5, 12, 20))

        if is_talking:
            m_size = abs(math.sin(timer * 1.5)) * 30 + 5
            if emotion == "shock": m_size = 45
            if emotion == "angry": m_size = 40
            pygame.draw.ellipse(surf, (180, 0, 0), (x - 20 + look_offset, head_y + 25, 40, m_size))
        else:
            pygame.draw.line(surf, (20,20,20), (x - 15 + look_offset, head_y + 35), (x + 15 + look_offset, head_y + 35), 6)

# ==========================================
# MAIN EXECUTION
# ==========================================
async def main():
    print("🚀 Auto Funny Video Generator Started...")
    
    current_story = fetch_and_delete_first_joke()
    if not current_story: return
        
    await download_voices(current_story)

    pygame.init()
    main_surf = pygame.Surface((WIDTH, HEIGHT))
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    
    try: 
        hindi_font = pygame.font.Font(FONT_PATH, 45)
        title_font = pygame.font.Font(FONT_PATH, 60)
    except: 
        hindi_font = pygame.font.SysFont("Arial", 45)
        title_font = pygame.font.SysFont("Arial", 60)

    loaded_bg = None
    bg_files = [f for f in os.listdir(BG_FOLDER) if f.endswith(('.png', '.jpg', '.jpeg'))]
    if bg_files:
        selected_bg_path = os.path.join(BG_FOLDER, random.choice(bg_files))
        loaded_bg = pygame.image.load(selected_bg_path)
        loaded_bg = pygame.transform.scale(loaded_bg, (WIDTH, HEIGHT))

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
        
        frames_to_render = int(speech_clip.duration * FPS) + 12 # 12 frame pause
        
        if "Wife" in chars:
            chars["Wife"].target_pos = [WIDTH//2 - 180, HEIGHT//2 + 100]
            chars["Wife"].flip = False
        if "Husband" in chars:
            chars["Husband"].target_pos = [WIDTH//2 + 180, HEIGHT//2 + 100]
            chars["Husband"].flip = True   

        for f in range(frames_to_render):
            timer += 1
            is_talking_now = f < int(speech_clip.duration * FPS)
            
            draw_background(main_surf, loaded_bg)
                
            for name, char in chars.items():
                is_talking = (name == speaker and is_talking_now)
                char.update()
                char.draw(main_surf, is_talking, emotion if is_talking else "normal", timer)
                
            pygame.draw.rect(main_surf, (255, 200, 0), (0, 40, WIDTH, 90))
            render_text_with_outline(main_surf, "Husband vs Wife 😂", title_font, (255, 255, 255), 110, 50, (0,0,0), 5)

            if is_talking_now:
                spk_color = (255, 100, 100) if emotion == "angry" else (255, 255, 100)
                render_text_with_outline(main_surf, f"{speaker}:", title_font, spk_color, 40, HEIGHT - 320, (0,0,0), 5)
                render_text_with_outline(main_surf, line['text'], hindi_font, (255, 255, 255), 40, HEIGHT - 230, (0,0,0), 4)

            # 🟢 नया: DYNAMIC ZOOM CAMERA (शॉक या गुस्से में चेहरे पर ज़ूम होगा)
            zoom_active = is_talking_now and emotion in ["angry", "shock"]
            
            if zoom_active:
                zoom_scale = 1.3
                new_w, new_h = int(WIDTH * zoom_scale), int(HEIGHT * zoom_scale)
                zoomed_surf = pygame.transform.smoothscale(main_surf, (new_w, new_h))
                
                # चेहरे को सेंटर में रखने की कोडिंग
                if speaker == "Wife": offset_x = 0  # Left Zoom
                else: offset_x = WIDTH - new_w      # Right Zoom
                offset_y = -200 # थोड़ा ऊपर की तरफ ज़ूम
                
                # Shake Effect in Zoom
                offset_x += random.randint(-10, 10)
                offset_y += random.randint(-10, 10)
                
                screen.fill((0,0,0))
                screen.blit(zoomed_surf, (offset_x, offset_y))
            else:
                screen.fill((0,0,0))
                screen.blit(main_surf, (0, 0))
            
            view = pygame.surfarray.array3d(screen)
            view = view.transpose([1, 0, 2])
            img_bgr = cv2.cvtColor(view, cv2.COLOR_RGB2BGR)
            video_writer.write(img_bgr)

    # 🟢 नया: Laugh Track के लिए एक्स्ट्रा 2 सेकंड स्क्रीन रोकें
    laugh_frames = 2 * FPS 
    for f in range(laugh_frames):
        timer += 1
        draw_background(main_surf, loaded_bg)
        for name, char in chars.items():
            char.update()
            char.draw(main_surf, False, "normal", timer)
        pygame.draw.rect(main_surf, (255, 200, 0), (0, 40, WIDTH, 90))
        render_text_with_outline(main_surf, "Husband vs Wife 😂", title_font, (255, 255, 255), 110, 50, (0,0,0), 5)
        
        screen.fill((0,0,0))
        screen.blit(main_surf, (0, 0))
        view = pygame.surfarray.array3d(screen)
        view = view.transpose([1, 0, 2])
        img_bgr = cv2.cvtColor(view, cv2.COLOR_RGB2BGR)
        video_writer.write(img_bgr)

    video_writer.release()
    pygame.quit()

    print("🎧 Merging Audio, BGM, and Laugh Track...")
    final_audio = concatenate_audioclips(audio_clips)
    
    # 🟢 नया: Laugh Track जोड़ें
    if os.path.exists(LAUGH_FILE):
        laugh_clip = AudioFileClip(LAUGH_FILE).fx(afx.volumex, 1.2)
        laugh_start_time = final_audio.duration
        # खाली ऑडियो बना कर लास्ट में लाफ ट्रैक जोड़ रहे हैं
        laugh_pad = AudioFileClip(LAUGH_FILE).fx(afx.volumex, 0).set_duration(laugh_frames / FPS) 
        final_audio = concatenate_audioclips([final_audio, laugh_clip.set_start(0).set_duration(laugh_frames / FPS)])

    if os.path.exists(BGM_FILE):
        bgm_clip = AudioFileClip(BGM_FILE).fx(afx.volumex, 0.12).loop(duration=final_audio.duration)
        final_audio = CompositeAudioClip([final_audio, bgm_clip])

    video_clip = VideoFileClip(temp_video_path)
    final_video = video_clip.set_audio(final_audio)

    final_video.write_videofile(final_video_path, codec="libx264", audio_codec="aac", fps=FPS, preset="ultrafast", logger=None)
    video_clip.close()
    
    print(f"✅ Video successfully saved at: {final_video_path}")

if __name__ == "__main__":
    asyncio.run(main())
