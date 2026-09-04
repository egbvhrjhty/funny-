import os, random, asyncio, re
from PIL import Image, ImageDraw, ImageFont
import edge_tts
from moviepy.editor import AudioFileClip, ColorClip, ImageClip, CompositeVideoClip, CompositeAudioClip

# =======================================================================
# 🟢 STORY SETTINGS 🟢
# =======================================================================
TOP_CENTER_TITLE = "Hindi Stories - हिंदी कहानियाँ"
VOICE_STORY = "hi-IN-MadhurNeural"   # मेल आवाज़ (फीमेल के लिए 'hi-IN-SwaraNeural')
VOICE_SPEED = "+0%"                   
HINDI_FONT = "./NirmalaB.ttf" 

OUTPUT_FOLDER = "./output"
TEMP_FOLDER = "./temp"
TEXT_FILE_PATH = "./stories.txt"
BG_FOLDER = "./bgs" 
CHAR_FOLDER = "./characters"

os.makedirs(OUTPUT_FOLDER, exist_ok=True)
os.makedirs(TEMP_FOLDER, exist_ok=True)
os.makedirs(BG_FOLDER, exist_ok=True)
os.makedirs(CHAR_FOLDER, exist_ok=True)

def get_wrapped_text_image(text, filename, max_width=60):
    try: font = ImageFont.truetype(HINDI_FONT, 70)
    except: font = ImageFont.load_default()
    
    words = text.split()
    lines = []; current_line = []
    
    for word in words:
        current_line.append(word)
        if len(" ".join(current_line)) > max_width:
            lines.append(" ".join(current_line[:-1]))
            current_line = [word]
    if current_line: lines.append(" ".join(current_line))
        
    dummy = Image.new('RGBA', (1, 1))
    draw = ImageDraw.Draw(dummy)
    
    line_heights = []; max_w = 0
    for line in lines:
        bbox = draw.textbbox((0, 0), line, font=font)
        max_w = max(max_w, bbox[2] - bbox[0])
        line_heights.append(bbox[3] - bbox[1])
        
    img_w = max_w + 100
    img_h = sum(line_heights) + (len(lines) * 20) + 100
    
    img = Image.new('RGBA', (img_w, img_h), (0, 0, 0, 180)) # Semi-transparent black background
    draw = ImageDraw.Draw(img)
    
    y_pos = 50
    for i, line in enumerate(lines):
        bbox = draw.textbbox((0, 0), line, font=font)
        x_pos = (img_w - (bbox[2] - bbox[0])) / 2
        draw.text((x_pos, y_pos), line, font=font, fill=(255, 255, 255, 255))
        y_pos += line_heights[i] + 20
        
    filepath = os.path.join(TEMP_FOLDER, filename)
    img.save(filepath)
    return ImageClip(filepath)

async def generate_voice(text, filename):
    filepath = os.path.join(TEMP_FOLDER, filename)
    communicate = edge_tts.Communicate(text, VOICE_STORY, rate=VOICE_SPEED, volume="+20%")
    await communicate.save(filepath)
    return filepath

def fetch_and_delete_first_story():
    if not os.path.exists(TEXT_FILE_PATH):
        print("❌ stories.txt फाइल नहीं मिली!")
        return None
        
    with open(TEXT_FILE_PATH, 'r', encoding='utf-8') as f:
        content = f.read()
        
    stories = [s.strip() for s in content.split("=====") if s.strip()]
    
    if not stories:
        print("❌ कोई कहानी नहीं बची है!")
        return None
        
    first_story = stories[0]
    remaining_stories = stories[1:]
    
    # Save remaining stories back
    with open(TEXT_FILE_PATH, 'w', encoding='utf-8') as f:
        f.write("\n=====\n".join(remaining_stories))
        
    return first_story

async def create_story_video(story_text):
    print("🎬 वीडियो रेंडरिंग शुरू हो रही है...")
    
    sentences = re.split(r'(?<=[।?!|.]) +|\n+', story_text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 2]
    
    bg_files = [f for f in os.listdir(BG_FOLDER) if f.endswith(('.png', '.jpg', '.jpeg'))]
    selected_bg = os.path.join(BG_FOLDER, random.choice(bg_files)) if bg_files else None
    
    char_files = [f for f in os.listdir(CHAR_FOLDER) if f.endswith(('.png'))]
    selected_char = os.path.join(CHAR_FOLDER, random.choice(char_files)) if char_files else None

    visual_clips = []
    audio_clips = []
    current_time = 0.0

    for i, sentence in enumerate(sentences):
        audio_path = await generate_voice(sentence, f"audio_{i}.mp3")
        audio_clip = AudioFileClip(audio_path)
        audio_clips.append(audio_clip.set_start(current_time))
        
        text_clip = get_wrapped_text_image(sentence, f"text_{i}.png", max_width=45)
        text_clip = text_clip.set_position(('center', 'center')).set_start(current_time).set_duration(audio_clip.duration + 0.5)
        visual_clips.append(text_clip)
        
        current_time += audio_clip.duration + 0.5

    total_duration = current_time + 1.0

    if selected_bg: bg_clip = ImageClip(selected_bg).resize((1920, 1080)).set_duration(total_duration).set_fps(24)
    else: bg_clip = ColorClip(size=(1920, 1080), color=(20, 20, 40)).set_duration(total_duration).set_fps(24)

    if selected_char:
        char_clip = ImageClip(selected_char).resize(height=600)
        char_clip = char_clip.set_position(('left', 'bottom')).set_duration(total_duration)
        all_visuals = [bg_clip, char_clip] + visual_clips
    else:
        all_visuals = [bg_clip] + visual_clips

    try: font = ImageFont.truetype(HINDI_FONT, 50)
    except: font = ImageFont.load_default()
    banner = get_wrapped_text_image(TOP_CENTER_TITLE, "banner.png", 50).set_position(('center', 30)).set_duration(total_duration)
    all_visuals.append(banner)

    final_audio = CompositeAudioClip(audio_clips)
    video = CompositeVideoClip(all_visuals).set_audio(final_audio)
    
    out_path = os.path.join(OUTPUT_FOLDER, "FINAL_UPLOAD.mp4")
    video.write_videofile(out_path, codec="libx264", audio_codec="aac", fps=24, preset="ultrafast", logger=None)
    
    return out_path

async def main():
    print("🚀 Test Mode Started: Timer disabled, YouTube upload disabled.")
    story = fetch_and_delete_first_story()
    if not story:
        return
    await create_story_video(story)
    print("✅ Video Successfully Created in output/ folder!")

if __name__ == "__main__":
    asyncio.run(main())
