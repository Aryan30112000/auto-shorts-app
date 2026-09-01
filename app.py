import streamlit as st
import os
import asyncio
import tempfile
import cv2
import numpy as np
from PIL import Image, ImageFilter
import google.generativeai as genai
import edge_tts
from moviepy.editor import ImageClip, AudioFileClip, TextClip, CompositeVideoClip

st.set_page_config(page_title="Auto Shorts Maker", layout="centered")
st.title("📱 Auto Shorts Generator (Pro)")

# 1. API Setup
if "GEMINI_API_KEY" in st.secrets:
    api_key = st.secrets["GEMINI_API_KEY"].strip()
    genai.configure(api_key=api_key)
else:
    st.error("API Key सेटिंग्स में नहीं मिली! कृपया Streamlit Secrets चेक करें।")
    st.stop()

# Helper: Logo Blur (Center Region Cleanup)
def remove_center_watermark(image_path, output_path):
    img = cv2.imread(image_path)
    h, w, _ = img.shape
    
    # पोस्टर के बीच का 10% हिस्सा जहाँ 'GK' लोगो है, उसे ब्लर करना
    ymin, ymax = int(h * 0.42), int(h * 0.58)
    xmin, xmax = int(w * 0.42), int(w * 0.58)
    
    sub_img = img[ymin:ymax, xmin:xmax]
    blurred = cv2.GaussianBlur(sub_img, (31, 31), 30)
    img[ymin:ymax, xmin:xmax] = blurred
    
    cv2.imwrite(output_path, img)
    return output_path

uploaded_file = st.file_uploader("अपना पोस्टर अपलोड करें", type=["jpg", "jpeg", "png"])

if uploaded_file and st.button("🚀 Video Generate Karein"):
    with st.spinner("AI वीडियो प्रोसेस कर रहा है (मोशन + सबटाइटल्स + लोगो क्लीन)..."):
        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                raw_img_path = os.path.join(tmpdir, "raw.jpg")
                clean_img_path = os.path.join(tmpdir, "clean.jpg")
                audio_path = os.path.join(tmpdir, "voice.mp3")
                output_vid_path = os.path.join(tmpdir, "short.mp4")

                with open(raw_img_path, "wb") as f:
                    f.write(uploaded_file.getbuffer())

                # 1. Clean Watermark
                remove_center_watermark(raw_img_path, clean_img_path)

                # 2. Script Generation
                pil_image = Image.open(clean_img_path)
                prompt = (
                    "इस पोस्टर को पढ़ो और केवल 15 सेकंड की आकर्षक, बोलने वाली हिंदी स्क्रिप्ट लिखो। "
                    "शुरुआत में सवाल हो और अंत में 'YES या NO कमेंट करें' कहें। "
                    "सिर्फ बोलने वाला टेक्स्ट दो, कोई निर्देश, ब्रैकेट या इमोजी नहीं।"
                )
                
                try:
                    model = genai.GenerativeModel("models/gemini-3.6-flash")
                    res = model.generate_content([pil_image, prompt])
                except Exception:
                    model = genai.GenerativeModel("gemini-3.6-flash")
                    res = model.generate_content([pil_image, prompt])

                script = res.text.strip()
                st.info(f"**जनरेटेड स्क्रिप्ट:**\n\n{script}")

                # 3. Voiceover (Edge-TTS)
                async def generate_audio():
                    comm = edge_tts.Communicate(script, voice="hi-IN-MadhurNeural")
                    await comm.save(audio_path)

                asyncio.run(generate_audio())

                # 4. Video & Motion Assembly
                audio = AudioFileClip(audio_path)
                dur = audio.duration

                # Blurred Background
                orig = Image.open(clean_img_path)
                bg_img = orig.resize((1080, 1920)).filter(ImageFilter.GaussianBlur(20))
                bg_p = os.path.join(tmpdir, "bg.jpg")
                bg_img.save(bg_p)
                
                bg_clip = ImageClip(bg_p).set_duration(dur)
                
                # Foreground with Gentle Zoom Motion
                fg_clip = ImageClip(clean_img_path).set_duration(dur)
                fg_clip = fg_clip.resize(width=1000)
                fg_clip = fg_clip.set_position("center")
                # Glitch-free smooth scale
                fg_clip = fg_clip.resize(lambda t: 1 + 0.04 * (t / dur))

                # 5. Captions / Subtitles Overlay
                # 3-4 टुकड़ों में टेक्स्ट दिखाना
                words = script.split()
                chunk_size = max(4, len(words) // 4)
                chunks = [" ".join(words[i:i + chunk_size]) for i in range(0, len(words), chunk_size)]
                
                subtitle_clips = []
                chunk_duration = dur / len(chunks)
                
                for idx, chunk in enumerate(chunks):
                    start_t = idx * chunk_duration
                    txt_clip = (TextClip(chunk, fontsize=48, color='yellow', font='DejaVu-Sans-Bold',
                                         stroke_color='black', stroke_width=3, method='caption', size=(900, None))
                                .set_position(('center', 1500))
                                .set_start(start_t)
                                .set_duration(chunk_duration))
                    subtitle_clips.append(txt_clip)

                # Composite All Elements
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

                # 6. Display & Download
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
