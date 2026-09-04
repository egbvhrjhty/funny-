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
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from google.auth.transport.requests import Request

# =====================================================================
# 🟢 1. EASY CUSTOMIZATION BLOCK 🟢
# =====================================================================
CHANNEL_NAME = "@AnimeJokesHindi"          # अपने चौथे चैनल का नाम
TOP_BANNER_TEXT = "Anime Comedy 😂"        # ऊपर दिखने वाला बैनर
FONT_PATH = "./NirmalaB.ttf"

# =====================================================================

OUTPUT_FOLDER = "./output"
TEMP_FOLDER = "./temp"
TEXT_FILE_PATH = "./jokes.txt"
BG_FOLDER = "./bgs" 
SFX_FOLDER = "./sfx"       
BGM_FILE = "./bgm.mp3"     
LAUGH_FILE = "./laugh.mp3" 
TOKENS_FOLDER = "./tokens"

os.makedirs(OUTPUT_FOLDER, exist_ok=True)
os.makedirs(TEMP_FOLDER, exist_ok=True)
os.makedirs(BG_FOLDER, exist_ok=True)
os.makedirs(SFX_FOLDER, exist_ok=True)
os.makedirs(TOKENS_FOLDER, exist_ok=True)

WIDTH, HEIGHT = 720, 1280
FPS = 30

# ==========================================
# 2. AUDIO GENERATION (ANIME STYLE VOICES)
# ==========================================
async def download_voices(story_lines):
    print("🎙️ Generating Anime Style Voices...")
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
            
            # 🟢 ANIME VOICE TUNING
            is_girl = (speaker.lower() == "girl")
            if is_girl:
                voice = "hi-IN-SwaraNeural"
                pitch = "+50Hz"   # Cute Kawaii Voice
                rate = "+15%"
            else:
                voice = "hi-IN-MadhurNeural"
                pitch = "-10Hz"   # Cool, deep Anime Boy Voice
                rate = "+5%"
            
            story_data.append({
                "scene": idx + 1,
                "speaker": "Girl" if is_girl else "Boy",
                "text": text,
                "voice": voice,
                "emotion": emotion,
                "camera": camera_cmd,
                "pitch": pitch,
                "rate": rate
            })
    return story_data

# ==========================================
# 4. YOUTUBE UPLOAD
# ==========================================
def upload_to_youtube(video_file):
    print("🌐 YouTube Uploading...")
    token_files = [os.path.join(TOKENS_FOLDER, f) for f in os.listdir(TOKENS_FOLDER) if f.endswith('.json')]
    if not token_files: return False
        
    yt_titles = ["Otaku Comedy 😂 | Anime Jokes Hindi", "Anime Boys vs Girls 🤣 | Funny Shorts", "ये Anime कार्टून देखकर हँसी नहीं रुकेगी 😆"]
    request_body = {
        "snippet": {
            "title": random.choice(yt_titles), 
            "description": "Funny Anime style comedy in Hindi! Subscribe for more! #anime #funny #hindi #shorts #otaku", 
            "tags": ["anime hindi", "funny anime", "hindi cartoon", "anime shorts", "comedy", "otaku"], 
            "categoryId": "24" # Entertainment
        },
        "status": {"privacyStatus": "public", "selfDeclaredMadeForKids": False}
    }

    for token_path in token_files:
        try:
            creds = Credentials.from_authorized_user_file(token_path, ["https://www.googleapis.com/auth/youtube.upload"])
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
                with open(token_path, 'w') as tf: tf.write(creds.to_json())
                    
            youtube = build('youtube', 'v3', credentials=creds)
            media = MediaFileUpload(video_file, chunksize=-1, resumable=True)
            request = youtube.videos().insert(part="snippet,status", body=request_body, media_body=media)
            response = request.execute()
            print(f"✅ Video LIVE: https://youtu.be/{response['id']}")
            return True
        except Exception as e: print(f"❌ Upload Error: {e}")
    return False

# ==========================================
# 5. DRAWING HELPERS
# ==========================================
def render_text_with_outline(surf, text, font, color, x, y, outline_color=(0,0,0), thickness=3, center_x=False):
    words = text.split(" ")
    lines, current_line = [], ""
    for word in words:
        test_line = current_line + word + " "
        if font.size(test_line)[0] < WIDTH - 80: current_line = test_line
        else: lines.append(current_line); current_line = word + " "
    lines.append(current_line)
    
    for i, line in enumerate(lines):
        final_x = x
        if center_x: final_x = (WIDTH - font.size(line)[0]) // 2
        for dx in range(-thickness, thickness + 1):
            for dy in range(-thickness, thickness + 1):
                if dx != 0 or dy != 0:
                    txt_bg = font.render(line, True, outline_color)
                    surf.blit(txt_bg, (final_x + dx, y + i * 55 + dy))
        txt_fg = font.render(line, True, color)
        surf.blit(txt_fg, (final_x, y + i * 55))

# ==========================================
# 🟢 6. ANIME CHARACTER CLASS 🟢
# ==========================================
class AnimeCharacter:
    def __init__(self, name, char_type):
        self.name = name
        self.char_type = char_type 
        
        self.skin_color = (255, 228, 215) # Pale Anime Skin
        
        if self.char_type == 'boy':
            self.jacket_color = (60, 90, 130)  # Denim Blue
            self.shirt_color = (30, 30, 30)    # Black inner shirt
            self.hair_color = (20, 20, 30)     # Dark Spiky Hair
            self.eye_color = (150, 40, 40)     # Red/Brown sharp eyes
        else:
            self.dress_color = (255, 170, 190) # Pink Dress
            self.hair_color = (90, 50, 30)     # Brown Hair
            self.eye_color = (120, 70, 30)     # Big Hazel Eyes
            self.headphone_color = (255, 100, 150) # Pink Headphones

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
            if self.blink_timer > 160: self.is_blinking = False; self.blink_timer = 0

    def draw(self, surf, is_talking, char_emotion, timer, action_frame):
        world_x, world_y = int(self.pos[0]), int(self.pos[1])
        char_surf = pygame.Surface((400, 560), pygame.SRCALPHA)
        cx, cy = 200, 240

        angle = 0; y_off = 0; is_hitting = False
        hit_dir = 1 if not self.flip else -1
        
        # Action Animations
        if action_frame >= 0:
            if char_emotion in ["slap", "punch"]:
                if action_frame < 15: is_hitting = True
            elif char_emotion == "victim":
                if action_frame < 10:
                    progress = action_frame / 10.0; angle = -90 * progress if self.flip else 90 * progress; y_off = 150 * progress
                elif action_frame < 35: angle = -90 if self.flip else 90; y_off = 150
                elif action_frame < 50:
                    progress = (action_frame - 35) / 15.0; angle = (-90 if self.flip else 90) * (1.0 - progress); y_off = 150 * (1.0 - progress)
            elif char_emotion in ["shock", "funny"]:
                if action_frame < 25: y_off = -abs(math.sin(action_frame * 0.8)) * 80 

        # Shadow
        pygame.draw.ellipse(surf, (0,0,0,80), (world_x-70, world_y+180, 140, 30))

        # 🟢 Girl Back Hair
        if self.char_type == 'girl':
            pygame.draw.ellipse(char_surf, self.hair_color, (cx-85, cy-120, 170, 220))

        # 🟢 Body
        pygame.draw.line(char_surf, (20,20,20), (cx - 30, cy + 160), (cx - 30, cy + 190), 12)
        pygame.draw.line(char_surf, (20,20,20), (cx + 30, cy + 160), (cx + 30, cy + 190), 12)

        if self.char_type == 'boy':
            # Denim Jacket Open with Inner Shirt
            pygame.draw.rect(char_surf, self.shirt_color, (cx-50, cy, 100, 160), border_radius=10)
            pygame.draw.rect(char_surf, self.jacket_color, (cx-65, cy, 40, 160), border_radius=10) # Left Jacket Flap
            pygame.draw.rect(char_surf, self.jacket_color, (cx+25, cy, 40, 160), border_radius=10) # Right Jacket Flap
        else:
            # Pink Dress
            pygame.draw.rect(char_surf, self.dress_color, (cx-55, cy, 110, 160), border_radius=20)
            pygame.draw.rect(char_surf, (20,20,20), (cx-55, cy, 110, 160), 4, border_radius=20)

        # 🟢 Arms
        arm_swing = math.sin(timer * 0.5) * 20 if is_talking else 0
        if char_emotion == "angry" and is_talking: arm_swing = math.sin(timer * 2.0) * 40
        
        arm_color = self.jacket_color if self.char_type == 'boy' else self.skin_color
        
        if is_hitting:
            pygame.draw.line(char_surf, arm_color, (cx, cy + 40), (cx + (140 * hit_dir), cy + 20), 18)
            pygame.draw.circle(char_surf, self.skin_color, (int(cx + (140 * hit_dir)), cy + 20), 22)
        else:
            pygame.draw.line(char_surf, arm_color, (cx - 60, cy + 40), (cx - 90, cy + 90 + arm_swing), 15)
            pygame.draw.line(char_surf, arm_color, (cx + 60, cy + 40), (cx + 90, cy + 90 - arm_swing), 15)
            pygame.draw.circle(char_surf, self.skin_color, (cx - 90, int(cy + 90 + arm_swing)), 16)
            pygame.draw.circle(char_surf, self.skin_color, (cx + 90, int(cy + 90 - arm_swing)), 16)

        # 🟢 Head & Face
        head_bounce = math.sin(timer * 1.5) * 5 if is_talking else 0
        head_y = cy - 65 + head_bounce
        
        # Anime Pointy Chin
        pygame.draw.polygon(char_surf, self.skin_color, [(cx-60, head_y), (cx+60, head_y), (cx, head_y+80)])
        pygame.draw.circle(char_surf, self.skin_color, (cx, head_y), 60)
        
        # Blush
        pygame.draw.ellipse(char_surf, (255, 150, 150, 100), (cx-55, head_y+20, 30, 15))
        pygame.draw.ellipse(char_surf, (255, 150, 150, 100), (cx+25, head_y+20, 30, 15))

        # 🟢 Eyes (Anime Sparkle Eyes)
        look = -10 if self.flip else 10
        if char_emotion == "victim" and 0 <= action_frame < 50:
            for ex in [-25, 25]:
                pygame.draw.line(char_surf, (20,20,20), (cx+ex-12+look, head_y-10), (cx+ex+12+look, head_y+10), 4)
                pygame.draw.line(char_surf, (20,20,20), (cx+ex+12+look, head_y-10), (cx+ex-12+look, head_y+10), 4)
        elif self.is_blinking:
            pygame.draw.line(char_surf, (20,20,20), (cx-40+look, head_y-5), (cx-10+look, head_y-5), 4)
            pygame.draw.line(char_surf, (20,20,20), (cx+10+look, head_y-5), (cx+40+look, head_y-5), 4)
        else:
            if self.char_type == 'girl':
                # Big Kawaii Eyes
                pygame.draw.ellipse(char_surf, (255,255,255), (cx-40+look, head_y-25, 30, 45))
                pygame.draw.ellipse(char_surf, (255,255,255), (cx+10+look, head_y-25, 30, 45))
                # Iris
                pygame.draw.ellipse(char_surf, self.eye_color, (cx-35+look, head_y-15, 20, 30))
                pygame.draw.ellipse(char_surf, self.eye_color, (cx+15+look, head_y-15, 20, 30))
                # Sparkles
                pygame.draw.circle(char_surf, (255,255,255), (cx-28+look, head_y-5), 5)
                pygame.draw.circle(char_surf, (255,255,255), (cx+22+look, head_y-5), 5)
            else:
                # Cool Sharp Boy Eyes
                pygame.draw.line(char_surf, (20,20,20), (cx-45+look, head_y-15), (cx-15+look, head_y-5), 5) # Eyelid
                pygame.draw.line(char_surf, (20,20,20), (cx+15+look, head_y-5), (cx+45+look, head_y-15), 5)
                pygame.draw.circle(char_surf, self.eye_color, (cx-30+look, head_y-5), 8)
                pygame.draw.circle(char_surf, self.eye_color, (cx+30+look, head_y-5), 8)
                pygame.draw.circle(char_surf, (20,20,20), (cx-30+look, head_y-5), 3) # Pupil
                pygame.draw.circle(char_surf, (20,20,20), (cx+30+look, head_y-5), 3)

        # 🟢 Mouth
        if is_talking:
            m_size = abs(math.sin(timer * 1.5)) * 15 + 5
            if char_emotion in ["shock", "slap"]: m_size = 25
            pygame.draw.ellipse(char_surf, (150, 40, 40), (cx-10+look, head_y+30, 20, m_size))
        else:
            pygame.draw.line(char_surf, (20,20,20), (cx-5+look, head_y+35), (cx+5+look, head_y+35), 3) # Tiny anime mouth

        # 🟢 Hair & Accessories
        if self.char_type == 'boy':
            # Spiky Anime Hair
            for hx in range(cx-70, cx+70, 20):
                pygame.draw.polygon(char_surf, self.hair_color, [(hx, head_y-40), (hx+20, head_y-120-random.randint(0,20)), (hx+40, head_y-40)])
            # Front Bangs
            pygame.draw.polygon(char_surf, self.hair_color, [(cx-30, head_y-50), (cx, head_y-10), (cx+30, head_y-50)])
        else:
            # Girl Front Bangs
            pygame.draw.ellipse(char_surf, self.hair_color, (cx-65, head_y-70, 130, 60))
            
            # 🟢 Kawaii Cat Headphones
            pygame.draw.arc(char_surf, (20,20,20), (cx-75, head_y-80, 150, 100), 0, math.pi, 8) # Headband
            # Cat Ears
            pygame.draw.polygon(char_surf, self.headphone_color, [(cx-60, head_y-70), (cx-40, head_y-120), (cx-20, head_y-70)])
            pygame.draw.polygon(char_surf, self.headphone_color, [(cx+20, head_y-70), (cx+40, head_y-120), (cx+60, head_y-70)])
            # Earpads
            pygame.draw.ellipse(char_surf, self.headphone_color, (cx-85, head_y-30, 30, 60))
            pygame.draw.ellipse(char_surf, self.headphone_color, (cx+55, head_y-30, 30, 60))
            pygame.draw.ellipse(char_surf, (20,20,20), (cx-85, head_y-30, 30, 60), 4)
            pygame.draw.ellipse(char_surf, (20,20,20), (cx+55, head_y-30, 30, 60), 4)

        # Apply rotation for falling
        if angle != 0:
            rotated_surf = pygame.transform.rotate(char_surf, angle)
            new_rect = rotated_surf.get_rect(center=(world_x, world_y + y_off))
            surf.blit(rotated_surf, new_rect.topleft)
        else:
            surf.blit(char_surf, (world_x - cx, world_y + y_off - cy))


# ==========================================
# 7. MAIN ENGINE
# ==========================================
async def main():
    print("🚀 Auto Anime Video Generator Started...")
    current_story = fetch_and_delete_first_joke()
    if not current_story: return
        
    await download_voices(current_story)

    pygame.init()
    try: 
        hindi_font = pygame.font.Font(FONT_PATH, 45)
        title_font = pygame.font.Font(FONT_PATH, 60)
        watermark_font = pygame.font.Font(FONT_PATH, 35)
    except: 
        hindi_font = pygame.font.SysFont("Arial", 45)
        title_font = pygame.font.SysFont("Arial", 60)
        watermark_font = pygame.font.SysFont("Arial", 35)

    world_w = WIDTH + 400 
    main_surf = pygame.Surface((world_w, HEIGHT))
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    
    loaded_bg = None
    bg_files = [f for f in os.listdir(BG_FOLDER) if f.endswith(('.png', '.jpg', '.jpeg'))]
    if bg_files:
        loaded_bg = pygame.image.load(os.path.join(BG_FOLDER, random.choice(bg_files)))
        loaded_bg = pygame.transform.scale(loaded_bg, (world_w, HEIGHT))

    temp_video_path = os.path.join(TEMP_FOLDER, "temp_video.mp4")
    final_video_path = os.path.join(OUTPUT_FOLDER, "FINAL_UPLOAD.mp4")
    fourcc = cv2.VideoWriter_fourcc(*'mp4v')
    video_writer = cv2.VideoWriter(temp_video_path, fourcc, FPS, (WIDTH, HEIGHT))

    chars = {
        "Girl": AnimeCharacter("Girl", "girl"),
        "Boy": AnimeCharacter("Boy", "boy")
    }
    
    audio_clips = []
    
    for idx, line in enumerate(current_story):
        speech_clip = AudioFileClip(line["audio"]).fx(afx.volumex, 4.0)
        if speech_clip.duration > 0.6: speech_clip = speech_clip.subclip(0, speech_clip.duration - 0.5)
            
        emotion = line.get("emotion", "normal")
        sfx_path = None
        if emotion != "normal":
            for ext in [".mp3", ".wav"]:
                if os.path.exists(os.path.join(SFX_FOLDER, f"{emotion}{ext}")):
                    sfx_path = os.path.join(SFX_FOLDER, f"{emotion}{ext}"); break

        if sfx_path:
            sfx_clip = AudioFileClip(sfx_path).fx(afx.volumex, 1.8)
            mixed_audio = CompositeAudioClip([speech_clip.set_start(0), sfx_clip.set_start(speech_clip.duration)])
            line["total_dur"] = speech_clip.duration + max(sfx_clip.duration, 1.8) 
            line["speech_dur"] = speech_clip.duration
            audio_clips.append(mixed_audio)
        else:
            line["total_dur"] = speech_clip.duration + 0.4 
            line["speech_dur"] = speech_clip.duration
            audio_clips.append(speech_clip)

    timer = 0; cam_x = 200 

    for idx, line in enumerate(current_story):
        speaker = line["speaker"]
        emotion = line.get("emotion", "normal")
        camera_cmd = line.get("camera", "normal") 
        
        frames_to_render = int(line["total_dur"] * FPS)
        speech_frames = int(line["speech_dur"] * FPS)
        
        chars["Girl"].target_pos = [world_w//2 - 180, HEIGHT//2 + 100]; chars["Girl"].flip = False
        chars["Boy"].target_pos = [world_w//2 + 180, HEIGHT//2 + 100]; chars["Boy"].flip = True   

        for f in range(frames_to_render):
            timer += 1
            is_talking_now = f < speech_frames
            action_frame = f - speech_frames
            is_action_time = action_frame >= 0
            
            if is_talking_now: target_cam_x = 100 if speaker == "Girl" else 300
            elif is_action_time and emotion in ["slap", "punch"]: target_cam_x = 300 if speaker == "Girl" else 100 
            else: target_cam_x = 200 
                
            cam_x += (target_cam_x - cam_x) * 0.1 
            
            if loaded_bg: main_surf.blit(loaded_bg, (0, 0))
            else: main_surf.fill((200, 100, 100)) # Anime Red BG Fallback
                
            for name, char in chars.items():
                is_talking = (name == speaker and is_talking_now)
                char.update()
                
                char_emotion = "normal"
                if name == speaker: char_emotion = emotion
                elif emotion in ["slap", "punch"] and is_action_time: char_emotion = "victim"
                
                char.draw(main_surf, is_talking, char_emotion, timer, action_frame)

            if is_action_time and emotion in ["slap", "punch"] and 0 <= action_frame <= 2:
                main_surf.fill((255, 255, 255), special_flags=pygame.BLEND_RGB_ADD)

            is_zoomed = "zoom" in camera_cmd and (is_talking_now or is_action_time)
            is_shaking = "shake" in camera_cmd and is_action_time
            
            if is_zoomed or is_shaking:
                zoom_scale = 1.3 if is_zoomed else 1.0
                new_w, new_h = int(world_w * zoom_scale), int(HEIGHT * zoom_scale)
                if is_zoomed:
                    zoomed_surf = pygame.transform.smoothscale(main_surf, (new_w, new_h))
                    zoom_offset_x = (new_w - world_w) // 2
                    zoom_offset_y = -200 
                else: zoomed_surf = main_surf; zoom_offset_x, zoom_offset_y = 0, 0
                
                if is_shaking:
                    shake_int = 25 if emotion in ["slap", "punch"] else 10
                    zoom_offset_x += random.randint(-shake_int, shake_int)
                    zoom_offset_y += random.randint(-shake_int, shake_int)
                
                screen.fill((0,0,0)); screen.blit(zoomed_surf, (-cam_x - zoom_offset_x, zoom_offset_y))
            else:
                screen.fill((0,0,0)); screen.blit(main_surf, (-int(cam_x), 0)) 
                
            watermark_surf = watermark_font.render(CHANNEL_NAME, True, (255, 255, 255))
            watermark_surf.set_alpha(120)
            screen.blit(watermark_surf, (20, 160))
            
            pygame.draw.rect(screen, (220, 50, 50), (0, 40, WIDTH, 90)) # Red Anime Banner
            render_text_with_outline(screen, TOP_BANNER_TEXT, title_font, (255, 255, 255), 0, 50, (0,0,0), 5, center_x=True)
            
            view = pygame.surfarray.array3d(screen); view = view.transpose([1, 0, 2])
            img_bgr = cv2.cvtColor(view, cv2.COLOR_RGB2BGR); video_writer.write(img_bgr)

    laugh_frames = 2 * FPS 
    for f in range(laugh_frames):
        timer += 1
        cam_x += (200 - cam_x) * 0.1 
        
        if loaded_bg: main_surf.blit(loaded_bg, (0, 0))
        else: main_surf.fill((200, 100, 100))
        for name, char in chars.items(): char.update(); char.draw(main_surf, False, "normal", timer, -1)
        
        screen.fill((0,0,0)); screen.blit(main_surf, (-int(cam_x), 0))
        
        pygame.draw.rect(screen, (220, 50, 50), (0, 40, WIDTH, 90))
        render_text_with_outline(screen, TOP_BANNER_TEXT, title_font, (255, 255, 255), 0, 50, (0,0,0), 5, center_x=True)

        view = pygame.surfarray.array3d(screen); view = view.transpose([1, 0, 2])
        img_bgr = cv2.cvtColor(view, cv2.COLOR_RGB2BGR); video_writer.write(img_bgr)

    video_writer.release()
    pygame.quit()

    print("🎧 Merging Audio...")
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
    
    upload_to_youtube(final_video_path)

if __name__ == "__main__":
    asyncio.run(main())
