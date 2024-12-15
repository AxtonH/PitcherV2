import streamlit as st
import openai
from PyPDF2 import PdfReader
from docx import Document
from pptx import Presentation
import io
import re
import tiktoken  # Install with pip install tiktoken

# OpenAI API configuration
openai.api_key = "AZXYFn1hLOH92KMjYRwc1mCUKQZevE043VPTlWooA"

# Constants for token limits
MAX_TOKENS = 8192
SAFE_TOKEN_LIMIT = 7000  # Reserve some tokens for the model's output

# Function to calculate token count for messages or text
def calculate_token_count(content, model="gpt-4"):
    enc = tiktoken.encoding_for_model(model)
    if isinstance(content, str):
        return len(enc.encode(content))
    elif isinstance(content, list):
        return sum([len(enc.encode(msg["content"])) for msg in content])
    return 0

# Function to summarize content that exceeds token limits
def summarize_text(content, model="gpt-4"):
    try:
        response = openai.ChatCompletion.create(
            model=model,
            messages=[{"role": "system", "content": "Summarize the following text briefly:"}, {"role": "user", "content": content}],
        )
        return response["choices"][0]["message"]["content"]
    except Exception as e:
        return f"Error summarizing text: {e}"

# Function to trim chat history to fit within token limits
def trim_or_summarize_chat_history(chat_history, model="gpt-4"):
    token_count = calculate_token_count(chat_history, model)
    while token_count > SAFE_TOKEN_LIMIT:
        if len(chat_history) > 2:
            # Summarize the oldest user and assistant message pair
            messages_to_summarize = chat_history[:2]
            summarized_content = summarize_text(
                "\n".join([msg["content"] for msg in messages_to_summarize]), model
            )
            chat_history = [{"role": "system", "content": f"Summary: {summarized_content}"}] + chat_history[2:]
            token_count = calculate_token_count(chat_history, model)
        else:
            break
    return chat_history

# Function to summarize text chunks if they exceed token limits
def process_text_chunks(chunks, model="gpt-4"):
    total_tokens = sum([calculate_token_count(chunk, model) for chunk in chunks])
    if total_tokens > SAFE_TOKEN_LIMIT:
        return [summarize_text("\n".join(chunks), model)]
    return chunks

# Function to extract text from files
def extract_text_from_file(file):
    if file.type == "text/plain":
        return file.read().decode("utf-8")
    elif file.type == "application/pdf":
        pdf_reader = PdfReader(file)
        return "\n".join([page.extract_text() for page in pdf_reader.pages])
    elif file.type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
        doc = Document(file)
        return "\n".join([para.text for para in doc.paragraphs])
    return None

# Function to chunk text into logical segments
def chunk_text(text, max_length=500):
    sentences = re.split(r'(?<=[.!?]) +', text)
    chunks = []
    current_chunk = ""
    for sentence in sentences:
        if len(current_chunk) + len(sentence) <= max_length:
            current_chunk += f"{sentence} "
        else:
            chunks.append(current_chunk.strip())
            current_chunk = sentence
    if current_chunk:
        chunks.append(current_chunk.strip())
    return chunks

# Define templates for Pitch Deck and Corporate Portfolio
def get_template(context_type):
    if context_type == "Pitch Deck":
        return ["Introduction", "Problem Statement", "Solution", "Key Features", "Market Opportunity", "Financials"]
    elif context_type == "Corporate Portfolio":
        return ["Company Overview", "Services/Products", "Achievements", "Team", "Contact Details"]
    return []

def parse_response_to_slides(ai_response, template):
    slides = []
    slide_number = 1
    response_chunks = ai_response.split("\n\n")

    for idx, title in enumerate(template):
        # Get the content for the current template section
        content = response_chunks[idx] if idx < len(response_chunks) else None

        # Clean and format the content into bullet points
        if content:
            content_points = [f"- {point.strip()}" for point in content.split(". ") if point.strip() and not point.startswith("http")]
            content = "\n".join(content_points).strip()
        else:
            content = ""  # Mark as empty if no content is available

        # Only add the slide if it has meaningful content
        if content:
            slides.append({"title": f"Slide {slide_number}: {title}", "content": content})
        else:
            # Optionally, add a placeholder for a missing section
            slides.append({"title": f"Slide {slide_number}: {title}", "content": "- Content not available for this slide."})

        slide_number += 1

    # Remove slides that only contain placeholder content (optional)
    slides = [slide for slide in slides if slide["content"].strip() != "- Content not available for this slide."]
    return slides

# Function to export slides into PowerPoint
def export_slides(slides):
    presentation = Presentation()
    for slide_info in slides:
        slide = presentation.slides.add_slide(presentation.slide_layouts[1])
        slide.shapes.title.text = slide_info.get("title", "Slide Title")
        content_shape = slide.placeholders[1]
        content_shape.text = "\n".join(slide_info.get("content", "").split("\n"))
    return presentation

# Streamlit App
st.set_page_config(page_title="🚀 Deck Generator & Slide Editor", layout="centered")

st.title("🚀 Professional Presentation Generator & Slide Editor")
st.caption("Turn your documents into engaging presentations and edit slides dynamically.")

# Initialize session state variables
if "slides" not in st.session_state:
    st.session_state.slides = []
if "current_presentation" not in st.session_state:
    st.session_state.current_presentation = None

# Radio button for context selection
context_type = st.radio(
    "What would you like to do?",
    options=["Pitch Deck", "Corporate Portfolio", "Chatbot"],
    index=0,
    horizontal=True
)

# Slide Editor
def display_slide_editor():
    if st.session_state.slides:
        st.subheader("📋 Edit Slides")
        for idx, slide in enumerate(st.session_state.slides):
            with st.expander(f"Edit {slide['title']}"):
                # Editable fields for slide title and content
                new_title = st.text_input(f"Slide {idx + 1} Title", slide["title"], key=f"title_{idx}")
                new_content = st.text_area(f"Slide {idx + 1} Content", slide["content"], height=150, key=f"content_{idx}")

                # Update the slide content dynamically
                if st.button(f"Save Changes to Slide {idx + 1}", key=f"save_{idx}"):
                    slide["title"] = new_title
                    slide["content"] = new_content
                    st.success(f"Slide {idx + 1} updated successfully!")

                    # Regenerate the PowerPoint with updated slides
                    st.session_state.current_presentation = export_slides(st.session_state.slides)
                    st.info("Presentation updated with the new slide content.")

        # Download the updated PowerPoint
        if st.session_state.current_presentation:
            ppt_bytes = io.BytesIO()
            st.session_state.current_presentation.save(ppt_bytes)
            ppt_bytes.seek(0)
            st.download_button(
                label="Download Updated Presentation",
                data=ppt_bytes,
                file_name="updated_presentation.pptx",
                mime="application/vnd.openxmlformats-officedocument.presentationml.presentation"
            )

# Context Logic
if context_type != "Chatbot":
    st.subheader("📂 Upload Document")
    uploaded_file = st.file_uploader("Choose a file (PDF, Word, or TXT)", type=["txt", "pdf", "docx"])

    if uploaded_file:
        file_content = extract_text_from_file(uploaded_file)
        if file_content:
            text_chunks = chunk_text(file_content)
            summarized_chunks = process_text_chunks(text_chunks)  # Summarize if needed

            if st.button("Generate Presentation"):
                with st.spinner("Generating slides..."):
                    system_context = (
                        f"You are an assistant for generating a professional {context_type}. "
                        f"Create content for the following sections: {', '.join(get_template(context_type))}."
                    )
                    response = openai.ChatCompletion.create(
                        model="gpt-4",
                        messages=[{"role": "system", "content": system_context}, {"role": "user", "content": "\n".join(summarized_chunks)}]
                    )
                    slides = parse_response_to_slides(response["choices"][0]["message"]["content"], get_template(context_type))
                    st.session_state.slides = slides
                    st.session_state.current_presentation = export_slides(slides)
                    st.success(f"{context_type} slides generated successfully!")

    display_slide_editor()

else:
    st.subheader("💬 Chat with Assistant")
    if "chat_history" not in st.session_state:
        st.session_state.chat_history = []

    user_input = st.chat_input("Type your message:")
    if user_input:
        st.session_state.chat_history.append({"role": "user", "content": user_input})
        st.session_state.chat_history = trim_or_summarize_chat_history(st.session_state.chat_history)

        with st.spinner("Assistant is typing..."):
            try:
                response = openai.ChatCompletion.create(
                    model="gpt-4",
                    messages=st.session_state.chat_history
                )
                reply = response["choices"][0]["message"]["content"]
                st.session_state.chat_history.append({"role": "assistant", "content": reply})
            except Exception as e:
                reply = f"Error: {e}"
                st.session_state.chat_history.append({"role": "assistant", "content": reply})

    if st.session_state.chat_history:
        for chat in st.session_state.chat_history:
            with st.chat_message(chat["role"]):
                st.markdown(chat["content"])   