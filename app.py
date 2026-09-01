import streamlit as st
import os
import asyncio
import tempfile
import cv2
import numpy as np
import random
import json
from PIL import Image, ImageFilter, ImageDraw, ImageFont
import google.generativeai as genai
import edge_tts
from moviepy.editor import ImageClip, AudioFileClip, CompositeVideoClip

st.set_page_config(page_title="Auto Shorts Maker Pro", layout="centered")
st.title("📱 AI Viral Shorts Maker")

# 1. API Setup
if "GEMINI_API_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_API_KEY"].strip()
    genai.configure(api_key=api_key)
else:
    st.error("API Key सेटिंग्स में नहीं मिली!")
    st.stop()

# Helper: Font Loader
def get_hindi_font(size=48):
    font_paths = [
        "/usr/share/fonts/truetype/lohit-devanagari/Lohit-Devanagari.ttf",
        "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
    ]
    for fp in font_paths:
        if os.path.exists(fp):
            try:
                return ImageFont.truetype(fp, size)
            except Exception:
                continue
    return ImageFont.load_default()

# Helper: AI Logo Inpainting (Telea Algorithm)
def inpaint_watermark(image_path, output_path):
    img = cv2.imread(image_path)
    h, w, _ = img.shape
    
    # ऑटो-मास्क: सेंटर लोगो रीजन को क्लीन रीकंस्ट्रक्ट करना
    mask = np.zeros((h, w), dtype=np.uint8)
    ymin, ymax = int(h * 0.38), int(h * 0.52)
    xmin, xmax = int(w * 0.42), int(w * 0.58)
    mask[ymin:ymax, xmin:xmax] = 255
    
    # इनपेंटिंग से लोगो रिमूव करके बैकग्राउंड मैच करना
    clean_img = cv2.inpaint(img, mask, inpaintRadius=7, flags=cv2.INPAINT_TELEA)
    
    # नीचे का अनचाहा पुराना टेक्स्ट क्रॉप
    cropped_clean = clean_img[int(h * 0.12):int(h * 0.74), 0:w]
    cv2.imwrite(output_path, cropped_clean)
    return output_path

# Helper: Top Yellow Hindi Headline Header
def create_top_header(title_text, output_path):
    canvas = Image.new("RGBA", (1080, 220), (255, 230, 0, 255))
    draw = ImageDraw.Draw(canvas)
    font = get_hindi_font(52)
    
    # रेड और ब्लैक का बोल्ड कॉम्बो
    bbox = draw.multiline_textbbox((0, 0), title_text, font=font, align="center")
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    
    x = (1080 - tw) // 2
    y = (220 - th) // 2
    
    draw.multiline_text((x, y), title_text, font=font, fill="#D32F2F", align="center", stroke_width=2, stroke_fill="#000000")
    canvas.save(output_path, "PNG")
    return output_path

# Helper: MrBeast Dynamic Pop-Up Captions (2-3 Words)
def create_popup_word_badge(text, output_path):
    canvas = Image.new("RGBA", (1080, 260), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    font = get_hindi_font(60)
    
    bbox = draw.textbbox((0, 0), text, font=font)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    
    w_box = tw + 80
    h_box = th + 40
    bx1 = (1080 - w_box) // 2
    by1 = (260 - h_box) // 2
    bx2, by2 = bx1 + w_box, by1 + h_box
    
    # डार्क सॉलिड कार्ड + नियॉन येलो ग्लो बॉर्डर
    draw.rounded_rectangle([bx1, by1, bx2, by2], radius=22, fill=(10, 10, 10, 240), outline="#00FFCC", width=4)
    draw.text(((1080 - tw) // 2, by1 + 15), text, font=font, fill="#FFE600", stroke_width=3, stroke_fill="#000000")
    
    canvas.save(output_path, "PNG")
    return output_path

# Helper: Particle Overlay (Ambient Dust/Sparkles)
def create_particle_frame(width=1080, height=1920, count=45):
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    for _ in range(count):
        x = random.randint(50, width - 50)
        y = random.randint(100, height - 100)
        r = random.randint(2, 6)
        alpha = random.randint(80, 200)
        draw.ellipse([x-r, y-r, x+r, y+r], fill=(255, 255, 255, alpha))
    return img

uploaded_file = st.file_uploader("अपना पोस्टर अपलोड करें", type=["jpg", "jpeg", "png"])

if uploaded_file and st.button("🚀 Generate Viral AI Short"):
    with st.spinner("AI वीडियो रेंडर हो रहा है (AI Inpainting + Dynamic Captions + Emotional Voice)..."):
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                raw_img_path = os.path.join(tmpdir, "raw.jpg")
                clean_img_path = os.path.join(tmpdir, "clean.jpg")
                top_header_path = os.path.join(tmpdir, "header.png")
                audio_path = os.path.join(tmpdir, "voice.mp3")
                output_vid_path = os.path.join(tmpdir, "viral_short.mp4")

                with open(raw_img_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())

                # 1. Inpaint Logo & Clean Poster
                inpaint_watermark(raw_img_path, clean_img_path)

                # 2. Gemini AI: Headline + High-Energy Hindi Script (JSON)
                pil_image = Image.open(raw_img_path)
                prompt = (
                    "इस पोस्टर को देखकर YouTube Shorts के लिए दो चीजें JSON फॉर्मेट में दो:\n"
                    "1. 'headline': 4-6 शब्दों की बहुत मसालेदार हिंदी हेडलाइन (जैसे: 'खान सर पर बड़ा खुलासा!').\n"
                    "2. 'script': 15 सेकंड का तेज़, सस्पेंस भरा हिंदी वॉइसओवर। शुरू में जोरदार हुक हो, बीच में खबर और अंत में 'YES या NO कमेंट करें'।\n"
                    "सिर्फ वैध JSON आउटपुट दो: {\"headline\": \"...\", \"script\": \"...\"}"
                )
                
                try:
                    model = genai.GenerativeModel("models/gemini-3.6-flash")
                    res = model.generate_content([pil_image, prompt])
                except Exception:
                    model = genai.GenerativeModel("gemini-3.6-flash")
                    res = model.generate_content([pil_image, prompt])

                raw_txt = res.text.replace("```json", "").replace("```", "").strip()
                data = json.loads(raw_txt)
                headline = data.get("headline", "बड़ी खबर: पूरा सच जानें!")
                script = data.get("script", "")

                st.info(f"**हेडलाइन:** {headline}\n\n**स्क्रिप्ट:** {script}")

                # 3. High-Emotion Hindi Voiceover (Pitch + Rate Optimized)
                async def generate_audio():
                    # +10% गति और +2Hz पिच से आवाज़ में एंकर जैसा उत्साह आता है
                    comm = edge_tts.Communicate(
                        script, 
                        voice="hi-IN-MadhurNeural",
                        rate="+12%", 
                        pitch="+3Hz"
                    )
                    await comm.save(audio_path)

                asyncio.run(generate_audio())

                # 4. Cinematic Motion Assembly
                audio = AudioFileClip(audio_path)
                dur = audio.duration

                # A. Blurred Ambient Background
                orig = Image.open(clean_img_path)
                bg_img = orig.resize((1080, 1920)).filter(ImageFilter.GaussianBlur(35))
                bg_p = os.path.join(tmpdir, "bg.jpg")
                bg_img.save(bg_p)
                bg_clip = ImageClip(bg_p).set_duration(dur)

                # B. Foreground Ken Burns (Smooth Zoom + Pan Motion)
                fg_clip = ImageClip(clean_img_path).set_duration(dur)
                fg_clip = fg_clip.resize(width=1020)
                fg_clip = fg_clip.set_position(("center", 260))
                fg_clip = fg_clip.resize(lambda t: 1 + 0.04 * (t / dur))

                # C. Top Yellow Hindi Header
                create_top_header(headline, top_header_path)
                header_clip = ImageClip(top_header_path).set_duration(dur).set_position(("center", 30))

                # D. Particle Ambient Layer
                part_img = create_particle_frame()
                part_p = os.path.join(tmpdir, "particles.png")
                part_img.save(part_p)
                part_clip = ImageClip(part_p).set_duration(dur).set_opacity(0.4)

                # E. MrBeast Style Dynamic Captions (Pop-Up Chunks)
                words = script.split()
                chunk_size = 3  # हर बार सिर्फ 2-3 शब्द स्क्रीन पर आएंगे
                chunks = [" ".join(words[i:i + chunk_size]) for i in range(0, len(words), chunk_size)]
                
                caption_clips = []
                chunk_duration = dur / len(chunks)
                
                for idx, chk in enumerate(chunks):
                    sub_p = os.path.join(tmpdir, f"pop_{idx}.png")
                    create_popup_word_badge(chk, sub_p)
                    
                    sub_clip = (ImageClip(sub_p)
                                .set_duration(chunk_duration)
                                .set_start(idx * chunk_duration)
                                .set_position(("center", 1400))
                                # Zoom Pop-in Animation
                                .resize(lambda t: min(1.0, 0.7 + 0.3 * (t * 6))))
                    caption_clips.append(sub_clip)

                # Composite All Elements
                final_video = CompositeVideoClip(
                    [bg_clip, fg_clip, part_clip, header_clip] + caption_clips, 
                    size=(1080, 1920)
                )
                final_video = final_video.set_audio(audio)

                final_video.write_videofile(
                    output_vid_path,
                    fps=24,
                    codec="libx264",
                    audio_codec="aac",
                    preset="ultrafast",
                    ffmpeg_params=["-pix_fmt", "yuv420p"]
                )

                # 5. Show & Download
                st.success("🎉 वायरल शॉर्ट्स तैयार है!")
                st.video(output_vid_path)
                
                with open(output_vid_path, "rb") as vid_file:
                    st.download_button(
                        label="📥 Download Video",
                        data=vid_file.read(),
                        file_name="viral_short.mp4",
                        mime="video/mp4"
                    )

        except Exception as e:
            st.error(f"Error: {e}")
