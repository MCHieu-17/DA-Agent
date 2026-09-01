from langchain_google_genai import ChatGoogleGenerativeAI


def create_gemini_llm(model: str, **options) -> ChatGoogleGenerativeAI:
    """Create a Gemini chat model with the configured model name."""
    return ChatGoogleGenerativeAI(model=model, **options)
