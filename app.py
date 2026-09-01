import streamlit as st
import os
import asyncio
import tempfile
import cv2
import numpy as np
from PIL import Image, ImageFilter, ImageDraw, ImageFont
import google.generativeai as genai
import edge_tts
from moviepy.editor import ImageClip, AudioFileClip, CompositeVideoClip

st.set_page_config(page_title="Auto Shorts Maker", layout="centered")
st.title("📱 Auto Shorts Generator (Pro)")

# 1. API Setup
if "GEMINI_API_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_API_KEY"].strip()
    genai.configure(api_key=api_key)
else:
    st.error("API Key सेटिंग्स में नहीं मिली! कृपया Streamlit Secrets चेक करें।")
    st.stop()

# Helper: Logo Blur (Targeting Center 'GK' Badge)
def remove_center_watermark(image_path, output_path):
    img = cv2.imread(image_path)
    h, w, _ = img.shape
    
    # सेंटर 'GK' लोगो का सटीक एरिया
    ymin, ymax = int(h * 0.44), int(h * 0.54)
    xmin, xmax = int(w * 0.44), int(w * 0.56)
    
    sub_img = img[ymin:ymax, xmin:xmax]
    blurred = cv2.GaussianBlur(sub_img, (65, 65), 50)
    img[ymin:ymax, xmin:xmax] = blurred
    
    cv2.imwrite(output_path, img)
    return output_path

# Helper: Clean Caption Bar (Bottom English Text Covering Box)
def create_subtitle_image(text, output_path, width=1080, height=360):
    # सॉलिड डार्क बैकग्राउंड बॉक्स जो नीचे वाले ओरिजिनल टेक्स्ट को पूरी तरह छुपा देगा
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    
    font_paths = [
        "/usr/share/fonts/truetype/lohit-devanagari/Lohit-Devanagari.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    ]
    font = None
    for fp in font_paths:
        if os.path.exists(fp):
            try:
                font = ImageFont.truetype(fp, 46)
                break
            except Exception:
                continue
    if font is None:
        font = ImageFont.load_default()

    words = text.split()
    lines, curr = [], []
    for w in words:
        curr.append(w)
        if len(" ".join(curr)) > 24:
            lines.append(" ".join(curr[:-1]))
            curr = [w]
    if curr:
        lines.append(" ".join(curr))

    full_text = "\n".join(lines)

    # सॉलिड ब्लैक स्ट्रिप ताकि नीचे का पोस्टर टेक्स्ट न दिखे
    draw.rectangle([20, 10, width - 20, height - 10], fill=(10, 10, 10, 245), outline=(255, 230, 0, 255), width=3)
    
    bbox = draw.multiline_textbbox((0, 0), full_text, font=font, align="center")
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    
    x = (width - text_w) // 2
    y = (height - text_h) // 2
    
    # वाइब्रेंट येलो टेक्स्ट
    draw.multiline_text((x, y), full_text, font=font, fill="#FFE600", align="center")
    
    img.save(output_path, "PNG")
    return output_path

uploaded_file = st.file_uploader("अपना पोस्टर अपलोड करें", type=["jpg", "jpeg", "png"])

if uploaded_file and st.button("🚀 Video Generate Karein"):
    with st.spinner("AI वीडियो प्रोसेस कर रहा है..."):
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                raw_img_path = os.path.join(tmpdir, "raw.jpg")
                clean_img_path = os.path.join(tmpdir, "clean.jpg")
                audio_path = os.path.join(tmpdir, "voice.mp3")
                output_vid_path = os.path.join(tmpdir, "short.mp4")

                with open(raw_img_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())

                # 1. Clean Logo
                remove_center_watermark(raw_img_path, clean_img_path)

                # 2. Script
                pil_image = Image.open(clean_img_path)
                prompt = (
                    "इस पोस्टर को पढ़ो और केवल 15 सेकंड की आकर्षक हिंदी स्क्रिप्ट लिखो। "
                    "शुरुआत में सवाल हो और अंत में 'YES या NO कमेंट करें' कहें। "
                    "सिर्फ बोलने वाला टेक्स्ट दो, कोई निर्देश या इमोजी नहीं।"
                )
                
                try:
                    model = genai.GenerativeModel("models/gemini-3.6-flash")
                    res = model.generate_content([pil_image, prompt])
                except Exception:
                    model = genai.GenerativeModel("gemini-3.6-flash")
                    res = model.generate_content([pil_image, prompt])

                script = res.text.strip()
                st.info(f"**जनरेटेड स्क्रिप्ट:**\n\n{script}")

                # 3. Voiceover
                async def generate_audio():
                    comm = edge_tts.Communicate(script, voice="hi-IN-MadhurNeural")
                    await comm.save(audio_path)

                asyncio.run(generate_audio())

                # 4. Video Assembly
                audio = AudioFileClip(audio_path)
                dur = audio.duration

                # Blurred Background
                orig = Image.open(clean_img_path)
                bg_img = orig.resize((1080, 1920)).filter(ImageFilter.GaussianBlur(30))
                bg_p = os.path.join(tmpdir, "bg.jpg")
                bg_img.save(bg_p)
                bg_clip = ImageClip(bg_p).set_duration(dur)
                
                # Foreground Poster (Centered & Clean)
                fg_clip = ImageClip(clean_img_path).set_duration(dur)
                fg_clip = fg_clip.resize(width=1040)
                fg_clip = fg_clip.set_position(("center", 180))

                # 5. Clean Hindi Captions (Placed over bottom text box)
                words = script.split()
                chunk_size = max(4, len(words) // 4)
                chunks = [" ".join(words[i:i + chunk_size]) for i in range(0, len(words), chunk_size)]
                
                subtitle_clips = []
                chunk_duration = dur / len(chunks)
                
                for idx, chunk in enumerate(chunks):
                    sub_img_path = os.path.join(tmpdir, f"sub_{idx}.png")
                    create_subtitle_image(chunk, sub_img_path)
                    
                    sub_clip = (ImageClip(sub_img_path)
                                .set_duration(chunk_duration)
                                .set_start(idx * chunk_duration)
                                .set_position(("center", 1420)))
                    subtitle_clips.append(sub_clip)

                # Composite Video
                final_video = CompositeVideoClip([bg_clip, fg_clip] + subtitle_clips, size=(1080, 1920))
                final_video = final_video.set_audio(audio)

                final_video.write_videofile(
                    output_vid_path,
                    fps=24,
                    codec="libx264",
                    audio_codec="aac",
                    preset="ultrafast",
                    ffmpeg_params=["-pix_fmt", "yuv420p"]
                )

                # 6. Show & Download
                st.success("🎉 वीडियो तैयार है!")
                st.video(output_vid_path)
                
                with open(output_vid_path, "rb") as vid_file:
                    st.download_button(
                        label="📥 Download Video",
                        data=vid_file.read(),
                        file_name="auto_short.mp4",
                        mime="video/mp4"
                    )

        except Exception as e:
            st.error(f"Error: {e}")
