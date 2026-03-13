import httpx
import logging
from app.config import settings

logger = logging.getLogger(__name__)

class WhatsAppService:
    """
    Service to interact with the Meta WhatsApp Cloud API.
    """

    def __init__(self):
        self.access_token = settings.whatsapp_access_token
        self.phone_number_id = settings.whatsapp_phone_number_id
        self.base_url = f"https://graph.facebook.com/v21.0/{self.phone_number_id}/messages"
        self.headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

    async def send_text_message(self, to_number: str, message_body: str) -> dict:
        """
        Sends a simple text message to a WhatsApp number.
        
        Args:
            to_number (str): The recipient's phone number in E.164 format (e.g., "1234567890").
            message_body (str): The text message to send.
            
        Returns:
            dict: The JSON response from the WhatsApp API.
        """
        if not self.access_token or not self.phone_number_id:
            logger.error("WhatsApp credentials missing in configuration.")
            return {"error": "Missing credentials"}

        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": to_number,
            "type": "text",
            "text": {"body": message_body}
        }

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.base_url,
                    headers=self.headers,
                    json=payload,
                    timeout=10.0
                )
                response.raise_for_status()
                data = response.json()
                logger.info(f"WhatsApp message sent to {to_number}: {data.get('messages', [{}])[0].get('id')}")
                return data
        except httpx.HTTPStatusError as e:
            logger.error(f"WhatsApp API error ({e.response.status_code}): {e.response.text}")
            return {"error": f"API error: {e.response.text}", "status_code": e.response.status_code}
        except Exception as e:
            logger.error(f"Unexpected error sending WhatsApp message: {str(e)}")
            return {"error": str(e)}

    async def send_template_message(
        self,
        to_number: str,
        template_name: str,
        language_code: str = "en_US",
        components: list = None
    ) -> dict:
        """
        Sends a template message to a WhatsApp number.
        Business-initiated conversations MUST use templates.
        
        Args:
            to_number (str): The recipient's phone number.
            template_name (str): Name of the approved template.
            language_code (str): Language code (e.g., "en_US").
            components (list, optional): Template components (parameters).
            
        Returns:
            dict: The JSON response from the WhatsApp API.
        """
        if not self.access_token or not self.phone_number_id:
            logger.error("WhatsApp credentials missing in configuration.")
            return {"error": "Missing credentials"}

        payload = {
            "messaging_product": "whatsapp",
            "to": to_number,
            "type": "template",
            "template": {
                "name": template_name,
                "language": {"code": language_code}
            }
        }
        if components:
            payload["template"]["components"] = components

        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.base_url,
                    headers=self.headers,
                    json=payload,
                    timeout=10.0
                )
                response.raise_for_status()
                data = response.json()
                logger.info(f"WhatsApp template '{template_name}' sent to {to_number}: {data.get('messages', [{}])[0].get('id')}")
                return data
        except httpx.HTTPStatusError as e:
            logger.error(f"WhatsApp API error ({e.response.status_code}): {e.response.text}")
            return {"error": f"API error: {e.response.text}", "status_code": e.response.status_code}
        except Exception as e:
            logger.error(f"Unexpected error sending WhatsApp template: {str(e)}")
            return {"error": str(e)}

# Singleton instance
whatsapp_service = WhatsAppService()
