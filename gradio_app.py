"""
🤖 PENNY V2.2 Gradio Interface
Hugging Face Space Entry Point

This file connects PENNY's backend to a Gradio chat interface,
allowing users to interact with PENNY through a web UI on Hugging Face Spaces.
"""

import gradio as gr
import logging
import sys
import asyncio
from typing import List, Tuple, Dict, Any
from datetime import datetime

# Setup logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# ============================================================
# IMPORT PENNY MODULES - FIXED FOR ACTUAL FILE STRUCTURE
# ============================================================

try:
    # Core orchestration - this is the main function we need
    from app.orchestrator import run_orchestrator
    
    # Intent classification
    from app.intents import IntentType
    
    logger.info("✅ Successfully imported PENNY modules from app/")
    
except ImportError as e:
    logger.error(f"❌ Failed to import PENNY modules: {e}")
    logger.error(f"   Make sure all files exist in app/ folder")
    logger.error(f"   Current error: {str(e)}")
    
    # Create fallback functions so the interface can still load
    async def run_orchestrator(message: str, context: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "reply": f"⚠️ PENNY is initializing. Please try again in a moment.\n\nError: {str(e)}",
            "intent": "error",
            "confidence": 0.0
        }
    
    def get_service_availability() -> Dict[str, bool]:
        return {
            "orchestrator": False,
            "weather_service": False,
            "event_database": False,
            "resource_finder": False
        }

# ============================================================
# SERVICE AVAILABILITY CHECK
# ============================================================

def get_service_availability() -> Dict[str, bool]:
    """
    Check which PENNY services are available.
    Returns dict of service_name -> availability status.
    """
    services = {}
    
    try:
        # Check if orchestrator is callable
        services["orchestrator"] = callable(run_orchestrator)
    except:
        services["orchestrator"] = False
    
    try:
        # Check if event/weather module loaded
        from app.event_weather import get_event_recommendations_with_weather
        services["weather_service"] = True
    except:
        services["weather_service"] = False
    
    try:
        # Check if event database accessible
        from app.location_utils import load_city_events
        services["event_database"] = True
    except:
        services["event_database"] = False
    
    try:
        # Check if tool agent loaded
        from app.tool_agent import handle_tool_request
        services["resource_finder"] = True
    except:
        services["resource_finder"] = False
    
    return services


# ============================================================
# SUPPORTED CITIES CONFIGURATION
# ============================================================

SUPPORTED_CITIES = [
    "Atlanta, GA",
    "Birmingham, AL", 
    "Chesterfield, VA",
    "El Paso, TX",
    "Norfolk, VA",
    "Providence, RI",
    "Seattle, WA"
]

def get_city_choices() -> List[str]:
    """Get list of supported cities for dropdown."""
    try:
        return ["Not sure / Other"] + sorted(SUPPORTED_CITIES)
    except Exception as e:
        logger.error(f"Error loading cities: {e}")
        return ["Not sure / Other", "Norfolk, VA"]


# ============================================================
# CHAT HANDLER
# ============================================================

async def chat_with_penny(
    message: str,
    city: str,
    history: List[Tuple[str, str]]
) -> Tuple[List[Tuple[str, str]], str]:
    """
    Process user message through PENNY's orchestrator and return response.
    
    Args:
        message: User's input text
        city: Selected city/location
        history: Chat history (list of (user_msg, bot_msg) tuples)
    
    Returns:
        Tuple of (updated_history, empty_string_to_clear_input)
    """
    if not message.strip():
        return history, ""
    
    try:
        # Build context from selected city
        context = {
            "timestamp": datetime.now().isoformat(),
            "conversation_history": history[-5:] if history else []  # Last 5 exchanges
        }
        
        # Add location if specified
        if city and city != "Not sure / Other":
            context["location"] = city
            context["tenant_id"] = city.split(",")[0].lower().replace(" ", "_")
        
        logger.info(f"📨 Processing: '{message[:60]}...' | City: {city}")
        
        # Call PENNY's orchestrator
        result = await run_orchestrator(message, context)
        
        # Extract response
        reply = result.get("reply", "I'm having trouble right now. Please try again! 💛")
        intent = result.get("intent", "unknown")
        confidence = result.get("confidence", 0.0)
        
        # Add to history
        history.append((message, reply))
        
        logger.info(f"✅ Response generated | Intent: {intent} | Confidence: {confidence:.2f}")
        
        return history, ""
        
    except Exception as e:
        logger.error(f"❌ Error processing message: {e}", exc_info=True)
        
        error_reply = (
            "I'm having trouble processing your request right now. "
            "Please try again in a moment! 💛\n\n"
            f"_Error: {str(e)[:100]}_"
        )
        history.append((message, error_reply))
        return history, ""


def chat_with_penny_sync(message: str, city: str, history: List[Tuple[str, str]]) -> Tuple[List[Tuple[str, str]], str]:
    """
    Synchronous wrapper for chat_with_penny to work with Gradio.
    Gradio expects sync functions, so we create an event loop here.
    """
    try:
        # Create new event loop for this call
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(chat_with_penny(message, city, history))
        loop.close()
        return result
    except Exception as e:
        logger.error(f"Error in sync wrapper: {e}")
        error_msg = f"Error: {str(e)}"
        history.append((message, error_msg))
        return history, ""


# ============================================================
# SERVICE STATUS DISPLAY
# ============================================================

def get_service_status() -> str:
    """Display current service availability status."""
    try:
        services = get_service_availability()
        status_lines = ["**🔧 PENNY Service Status:**\n"]
        
        service_names = {
            "orchestrator": "🧠 Core Orchestrator",
            "weather_service": "🌤️ Weather Service",
            "event_database": "📅 Event Database",
            "resource_finder": "🏛️ Resource Finder"
        }
        
        for service_key, available in services.items():
            icon = "✅" if available else "⚠️"
            status = "Online" if available else "Limited"
            name = service_names.get(service_key, service_key.replace('_', ' ').title())
            status_lines.append(f"{icon} **{name}**: {status}")
        
        return "\n".join(status_lines)
    except Exception as e:
        logger.error(f"Error getting service status: {e}")
        return "**⚠️ Status:** Unable to check service availability"


# ============================================================
# GRADIO UI DEFINITION
# ============================================================

# Custom CSS for enhanced styling
custom_css = """
#chatbot {
    height: 500px;
    overflow-y: auto;
    border-radius: 8px;
}
.gradio-container {
    font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
}
#status-panel {
    background: linear-gradient(135deg, #f5f7fa 0%, #c3cfe2 100%);
    padding: 15px;
    border-radius: 8px;
    margin: 10px 0;
}
footer {
    display: none !important;
}
.message-user {
    background-color: #e3f2fd !important;
}
.message-bot {
    background-color: #fff3e0 !important;
}
"""

# Build the Gradio interface
with gr.Blocks(
    theme=gr.themes.Soft(primary_hue="amber", secondary_hue="blue"),
    css=custom_css,
    title="PENNY V2.2 - Civic Assistant"
) as demo:
    
    # Header
    gr.Markdown(
        """
        # 🤖 PENNY V2.2 - People's Engagement Network Navigator for You
        
        **Your multilingual civic assistant connecting residents to local government services and community resources.**
        
        ### 💬 Ask me about:
        - 🌤️ **Weather conditions** and forecasts
        - 📅 **Community events** and activities
        - 🏛️ **Local resources** (shelters, libraries, food banks, healthcare)
        - 👥 **Elected officials** and government contacts
        - 🌍 **Translation** services (27+ languages)
        - 📄 **Document assistance** and form help
        """
    )
    
    with gr.Row():
        with gr.Column(scale=2):
            # City selector
            city_dropdown = gr.Dropdown(
                choices=get_city_choices(),
                value="Norfolk, VA",
                label="📍 Select Your City",
                info="Choose your city for location-specific information",
                interactive=True
            )
            
            # Chat interface
            chatbot = gr.Chatbot(
                label="💬 Chat with PENNY",
                elem_id="chatbot",
                avatar_images=(None, "🤖"),
                show_label=True,
                height=500,
                bubble_full_width=False
            )
            
            # Input row
            with gr.Row():
                msg_input = gr.Textbox(
                    placeholder="Type your message here... (e.g., 'What's the weather today?')",
                    show_label=False,
                    scale=4,
                    container=False,
                    lines=1
                )
                submit_btn = gr.Button("Send 📤", variant="primary", scale=1)
            
            # Clear button
            clear_btn = gr.Button("🗑️ Clear Chat", variant="secondary", size="sm")
            
            # Example queries
            gr.Examples(
                examples=[
                    ["What's the weather in Norfolk today?"],
                    ["Any community events this weekend?"],
                    ["I need help finding a food bank"],
                    ["Who is my city council representative?"],
                    ["Show me local libraries"],
                    ["Translate 'hello' to Spanish"],
                    ["Help me understand this document"]
                ],
                inputs=msg_input,
                label="💡 Try asking:"
            )
        
        with gr.Column(scale=1):
            # Service status panel
            status_display = gr.Markdown(
                value=get_service_status(),
                label="System Status",
                elem_id="status-panel"
            )
            
            # Refresh status button
            refresh_btn = gr.Button("🔄 Refresh Status", size="sm", variant="secondary")
            
            gr.Markdown(
                """
                ### 🌟 Key Features
                
                - ✅ **27+ Languages** supported
                - ✅ **Real-time weather** via Azure Maps
                - ✅ **Community events** database
                - ✅ **Local resource** finder
                - ✅ **Government contact** lookup
                - ✅ **Document processing** help
                - ✅ **Multilingual** support
                
                ---
                
                ### 📍 Supported Cities
                
                - Atlanta, GA
                - Birmingham, AL
                - Chesterfield, VA
                - El Paso, TX
                - Norfolk, VA
                - Providence, RI
                - Seattle, WA
                
                ---
                
                ### 🆘 Need Help?
                
                PENNY can assist with:
                - Finding emergency services
                - Locating government offices
                - Understanding civic processes
                - Accessing community programs
                
                ---
                
                💛 *PENNY is here to help connect you with civic resources!*
                """
            )
    
    # Event handlers
    submit_btn.click(
        fn=chat_with_penny_sync,
        inputs=[msg_input, city_dropdown, chatbot],
        outputs=[chatbot, msg_input]
    )
    
    msg_input.submit(
        fn=chat_with_penny_sync,
        inputs=[msg_input, city_dropdown, chatbot],
        outputs=[chatbot, msg_input]
    )
    
    clear_btn.click(
        fn=lambda: ([], ""),
        inputs=None,
        outputs=[chatbot, msg_input]
    )
    
    refresh_btn.click(
        fn=get_service_status,
        inputs=None,
        outputs=status_display
    )
    
    # Footer
    gr.Markdown(
        """
        ---
        **Built with:** Python • FastAPI • Gradio • Azure ML • Hugging Face Transformers
        
        **Version:** 2.2 | **Last Updated:** November 2025
        
        _PENNY is an open-source civic engagement platform designed to improve access to government services._
        """
    )


# ============================================================
# INITIALIZATION AND LAUNCH
# ============================================================

def initialize_penny():
    """Initialize PENNY services at startup."""
    logger.info("=" * 70)
    logger.info("🚀 Initializing PENNY V2.2 Gradio Interface")
    logger.info("=" * 70)
    
    # Display service availability at startup
    logger.info("\n📊 Service Availability Check:")
    services = get_service_availability()
    
    all_available = True
    for service, available in services.items():
        status = "✅ Available" if available else "❌ Not loaded"
        logger.info(f"  {service.ljust(20)}: {status}")
        if not available:
            all_available = False
    
    if all_available:
        logger.info("\n✅ All services loaded successfully!")
    else:
        logger.warning("\n⚠️ Some services are not available. PENNY will run with limited functionality.")
    
    logger.info("\n" + "=" * 70)
    logger.info("🤖 PENNY is ready to help residents!")
    logger.info("=" * 70 + "\n")


if __name__ == "__main__":
    # Initialize services
    initialize_penny()
    
    # Launch the Gradio app
    demo.launch(
        server_name="0.0.0.0",
        server_port=7860,
        share=False,
        show_error=True
    )