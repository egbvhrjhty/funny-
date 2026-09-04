import os
os.environ["SDL_VIDEODRIVER"] = "dummy"

import pygame
import math
import numpy as np
import asyncio
import random
import cv2
import re
from moviepy.editor import VideoFileClip, AudioFileClip, concatenate_audioclips, CompositeAudioClip
import moviepy.audio.fx.all as afx
import edge_tts

# ==========================================
# 🟢 1. SETTINGS & FOLDERS 🟢
# ==========================================
OUTPUT_FOLDER = "./output"
TEMP_FOLDER = "./temp"
TEXT_FILE_PATH = "./jokes.txt"
BG_FOLDER = "./bgs" 
SFX_FOLDER = "./sfx"       
BGM_FILE = "./bgm.mp3"     
LAUGH_FILE = "./laugh.mp3" 

os.makedirs(OUTPUT_FOLDER, exist_ok=True)
os.makedirs(TEMP_FOLDER, exist_ok=True)
os.makedirs(BG_FOLDER, exist_ok=True)
os.makedirs(SFX_FOLDER, exist_ok=True)

WIDTH, HEIGHT = 720, 1280
FPS = 30

char_colors = {
    "Wife": (255, 105, 180),
    "Husband": (100, 200, 100)
}

# ==========================================
# 2. AUDIO GENERATION 
# ==========================================
async def download_voices(story_lines):
    print("🎙️ Generating AI Voices...")
    for i, line in enumerate(story_lines):
        filename = os.path.join(TEMP_FOLDER, f"temp_audio_{i}.mp3")
        line["audio"] = filename
        communicate = edge_tts.Communicate(line["text"], line["voice"], rate=line["rate"], pitch=line["pitch"], volume="+100%")
        await communicate.save(filename)

# ==========================================
# 3. TEXT PARSING 
# ==========================================
def fetch_and_delete_first_joke():
    if not os.path.exists(TEXT_FILE_PATH): return None
    with open(TEXT_FILE_PATH, 'r', encoding='utf-8') as f:
        content = f.read()
        
    jokes = [s.strip() for s in content.split("=====") if s.strip()]
    if not jokes: return None
        
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
            bracket_content = match.group(2).strip().lower() if match.group(2) else "normal"
            text = match.group(3).strip()
            
            bracket_parts = [p.strip() for p in bracket_content.split(',')]
            emotion = bracket_parts[0] if len(bracket_parts) > 0 else "normal"
            camera_cmd = bracket_parts[1] if len(bracket_parts) > 1 else "normal"
            
            is_wife = (speaker.lower() == "wife")
            voice = "hi-IN-SwaraNeural" if is_wife else "hi-IN-MadhurNeural"
            pitch = "+45Hz" if is_wife else "+35Hz" 
            rate = "+25%" if is_wife else "+20%"
            
            story_data.append({
                "scene": idx + 1,
                "speaker": "Wife" if is_wife else "Husband",
                "text": text,
                "voice": voice,
                "emotion": emotion,
                "camera": camera_cmd,
                "pitch": pitch,
                "rate": rate
            })
    return story_data

# ==========================================
# 4. DRAWING FUNCTIONS
# ==========================================
def draw_background(surf, bg_img):
    if bg_img: surf.blit(bg_img, (0, 0))
    else: surf.fill((160, 140, 240)) 

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

    def draw(self, surf, is_talking, emotion, timer, is_action_time):
        x, y = int(self.pos[0]), int(self.pos[1])
        
        # कैरेक्टर का उछलना (Jump) सिर्फ SFX के समय (Last में) होगा
        if emotion in ["shock", "slap", "punch", "funny"] and is_action_time: 
            y -= abs(math.sin(timer * 0.8)) * 40 
            
        body_y = y 
        arm_swing = math.sin(timer * 0.5) * 20 if is_talking else 0
        
        pygame.draw.ellipse(surf, (0,0,0,80), (x-70, self.pos[1]+180, 140, 30))
        pygame.draw.line(surf, (20,20,20), (x - 30, body_y + 160), (x - 30, self.pos[1] + 190), 12)
        pygame.draw.line(surf, (20,20,20), (x + 30, body_y + 160), (x + 30, self.pos[1] + 190), 12)
        pygame.draw.rect(surf, self.color, (x-60, body_y, 120, 160), border_radius=30)
        pygame.draw.rect(surf, (20,20,20), (x-60, body_y, 120, 160), 6, border_radius=30)

        if emotion in ["angry", "slap"] and is_talking: arm_swing = math.sin(timer * 2.0) * 40
        pygame.draw.line(surf, (20,20,20), (x - 60, body_y + 50), (x - 90, body_y + 90 + arm_swing), 12)
        pygame.draw.line(surf, (20,20,20), (x + 60, body_y + 50), (x + 90, body_y + 90 - arm_swing), 12)

        head_bounce = math.sin(timer * 1.5) * 5 if is_talking else 0
        head_y = body_y - 60 + head_bounce
        
        face_color = (255, 120, 120) if emotion in ["angry", "slap"] else (255, 220, 180)
        pygame.draw.circle(surf, face_color, (x, head_y), 70)
        pygame.draw.circle(surf, (20,20,20), (x, head_y), 70, 6)

        eye_w, eye_h = 20, (4 if self.is_blinking else 30)
        look_offset = -10 if self.flip else 10
        if emotion in ["shock", "slap", "punch"]: eye_h = 50
        
        pygame.draw.ellipse(surf, (20,20,20), (x - 30 + look_offset, head_y - 20, eye_w, eye_h))
        pygame.draw.ellipse(surf, (20,20,20), (x + 10 + look_offset, head_y - 20, eye_w, eye_h))
        
        if emotion in ["angry", "slap"]:
            pygame.draw.line(surf, (20,20,20), (x - 40 + look_offset, head_y - 35), (x - 15 + look_offset, head_y - 15), 5)
            pygame.draw.line(surf, (20,20,20), (x + 35 + look_offset, head_y - 35), (x + 10 + look_offset, head_y - 15), 5)
            pygame.draw.line(surf, (200,0,0), (x + 20, head_y - 50), (x + 40, head_y - 30), 4)
            pygame.draw.line(surf, (200,0,0), (x + 40, head_y - 50), (x + 20, head_y - 30), 4)

        if emotion in ["sad", "cry"]: 
            pygame.draw.ellipse(surf, (0, 191, 255), (x + 30 + look_offset, head_y - 5, 12, 20))

        # 🟢 मुँह की कोडिंग: is_talking False होते ही तुरंत बंद हो जाएगा
        if is_talking:
            m_size = abs(math.sin(timer * 1.5)) * 30 + 5
            if emotion in ["shock", "slap"]: m_size = 45
            if emotion == "angry": m_size = 40
            pygame.draw.ellipse(surf, (180, 0, 0), (x - 20 + look_offset, head_y + 25, 40, m_size))
        else:
            pygame.draw.line(surf, (20,20,20), (x - 15 + look_offset, head_y + 35), (x + 15 + look_offset, head_y + 35), 6)

# ==========================================
# 5. MAIN EXECUTION
# ==========================================
async def main():
    print("🚀 Auto Video Generator Started...")
    
    current_story = fetch_and_delete_first_joke()
    if not current_story: return
        
    await download_voices(current_story)

    pygame.init()
    main_surf = pygame.Surface((WIDTH, HEIGHT))
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    
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
    
    for idx, line in enumerate(current_story):
        speech_clip = AudioFileClip(line["audio"]).fx(afx.volumex, 4.0)
        
        # 🟢 SILENCE TRIMMER (मूह 1 सेकंड हिलने वाले बग का इलाज)
        # AI Voice फाइल के लास्ट में 0.5 सेकंड की शांति जोड़ देता है। हम उसे काट रहे हैं।
        trim_amount = 0.5 
        if speech_clip.duration > (trim_amount + 0.2):
            speech_clip = speech_clip.subclip(0, speech_clip.duration - trim_amount)
            
        emotion = line.get("emotion", "normal")
        
        sfx_path = None
        if emotion != "normal":
            mp3_path = os.path.join(SFX_FOLDER, f"{emotion}.mp3")
            wav_path = os.path.join(SFX_FOLDER, f"{emotion}.wav")
            if os.path.exists(mp3_path): sfx_path = mp3_path
            elif os.path.exists(wav_path): sfx_path = wav_path

        if sfx_path:
            sfx_clip = AudioFileClip(sfx_path).fx(afx.volumex, 1.8)
            mixed_audio = CompositeAudioClip([
                speech_clip.set_start(0), 
                sfx_clip.set_start(speech_clip.duration) # SFX बिल्कुल आवाज़ खत्म होने पर बजेगा
            ])
            line["total_dur"] = speech_clip.duration + sfx_clip.duration + 0.2
            line["speech_dur"] = speech_clip.duration
            audio_clips.append(mixed_audio)
        else:
            line["total_dur"] = speech_clip.duration + 0.4 
            line["speech_dur"] = speech_clip.duration
            audio_clips.append(speech_clip)

    print("🎥 Rendering Video Frames...")
    for idx, line in enumerate(current_story):
        speaker = line["speaker"]
        emotion = line.get("emotion", "normal")
        camera_cmd = line.get("camera", "normal") 
        
        frames_to_render = int(line["total_dur"] * FPS)
        speech_frames = int(line["speech_dur"] * FPS)
        
        if "Wife" in chars:
            chars["Wife"].target_pos = [WIDTH//2 - 180, HEIGHT//2 + 100]
            chars["Wife"].flip = False
        if "Husband" in chars:
            chars["Husband"].target_pos = [WIDTH//2 + 180, HEIGHT//2 + 100]
            chars["Husband"].flip = True   

        for f in range(frames_to_render):
            timer += 1
            is_talking_now = f < speech_frames
            is_action_time = f >= speech_frames
            
            draw_background(main_surf, loaded_bg)
                
            for name, char in chars.items():
                is_talking = (name == speaker and is_talking_now)
                char.update()
                char.draw(main_surf, is_talking, emotion if name == speaker else "normal", timer, is_action_time)
                
            # 🟢 CAMERA ZOOM / SHAKE LOGIC (Starting of the voice)
            # अगर प्रॉम्प्ट में zoom या shake है, तो वो आवाज़ के साथ (is_talking_now) चलेगा
            is_zoomed = "zoom" in camera_cmd and is_talking_now
            is_shaking = "shake" in camera_cmd and is_talking_now
            
            if is_zoomed or is_shaking:
                zoom_scale = 1.3 if is_zoomed else 1.0
                new_w, new_h = int(WIDTH * zoom_scale), int(HEIGHT * zoom_scale)
                
                if is_zoomed:
                    zoomed_surf = pygame.transform.smoothscale(main_surf, (new_w, new_h))
                    offset_x = 0 if speaker == "Wife" else WIDTH - new_w      
                    offset_y = -200 
                else:
                    zoomed_surf = main_surf
                    offset_x, offset_y = 0, 0
                
                if is_shaking:
                    shake_intensity = 15 if emotion in ["slap", "punch"] else 8
                    offset_x += random.randint(-shake_intensity, shake_intensity)
                    offset_y += random.randint(-shake_intensity, shake_intensity)
                
                screen.fill((0,0,0))
                screen.blit(zoomed_surf, (offset_x, offset_y))
            else:
                screen.fill((0,0,0))
                screen.blit(main_surf, (0, 0))
            
            view = pygame.surfarray.array3d(screen)
            view = view.transpose([1, 0, 2])
            img_bgr = cv2.cvtColor(view, cv2.COLOR_RGB2BGR)
            video_writer.write(img_bgr)

    laugh_frames = 2 * FPS 
    for f in range(laugh_frames):
        timer += 1
        draw_background(main_surf, loaded_bg)
        for name, char in chars.items():
            char.update()
            char.draw(main_surf, False, "normal", timer, False)
        
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
    
    if os.path.exists(LAUGH_FILE):
        laugh_clip = AudioFileClip(LAUGH_FILE).fx(afx.volumex, 1.2)
        final_audio = concatenate_audioclips([final_audio, laugh_clip.set_start(0).set_duration(laugh_frames / FPS)])

    if os.path.exists(BGM_FILE):
        bgm_clip = AudioFileClip(BGM_FILE).fx(afx.volumex, 0.15).loop(duration=final_audio.duration)
        final_audio = CompositeAudioClip([final_audio, bgm_clip])

    video_clip = VideoFileClip(temp_video_path)
    final_video = video_clip.set_audio(final_audio)

    final_video.write_videofile(final_video_path, codec="libx264", audio_codec="aac", fps=FPS, preset="ultrafast", logger=None)
    video_clip.close()
    
    print(f"✅ CLEAN & PERFECT VIDEO successfully saved at: {final_video_path}")

if __name__ == "__main__":
    asyncio.run(main())
