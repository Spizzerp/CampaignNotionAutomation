# automation.py
import os
from notion_client import Client
from dotenv import load_dotenv
from datetime import datetime
import re
import requests
from urllib.parse import urlparse
import json
import boto3

# Load environment variables
load_dotenv()

class NotionAutomation:
    def __init__(self):
        self.notion = Client(auth=os.getenv("NOTION_TOKEN"))
        self.campaign_db_id = os.getenv("CAMPAIGN_STRATEGY_DB_ID")
        self.content_db_id = os.getenv("CONTENT_CALENDAR_DB_ID")

    def validate_url(self, url):
        """Validate if URL is accessible and returns proper content"""
        try:
            # Parse the URL
            parsed = urlparse(url)
            if not all([parsed.scheme, parsed.netloc]):
                print("❌ Invalid URL format")
                return False

            # Skip validation for Notion S3 URLs
            if 'prod-files-secure.s3' in url:
                print("⚠️ Skipping validation for Notion-hosted file")
                return True

            # Try to fetch headers only
            response = requests.head(url, allow_redirects=True, timeout=5)
            
            # Check if successful
            if response.status_code != 200:
                print(f"❌ URL returned status code: {response.status_code}")
                return False

            # Check content type
            content_type = response.headers.get('content-type', '').lower()
            if 'image' in content_type:
                print("✅ Valid image URL")
                return True
            elif 'video' in content_type:
                print("✅ Valid video URL")
                return True
            else:
                print(f"❌ Invalid content type: {content_type}")
                return False

        except requests.exceptions.RequestException as e:
            print(f"❌ URL validation error: {e}")
            return False
        except Exception as e:
            print(f"❌ Unexpected error during URL validation: {e}")
            return False

    def debug_media_block(self, block):
        """Debug helper for media blocks"""
        try:
            block_type = block["type"]
            media_data = block[block_type]
            
            print("\n=== Debug Media Block ===")
            print(f"Block Type: {block_type}")
            print(f"Media Type: {media_data['type']}")
            
            if media_data["type"] == "file":
                print("File URL:", media_data["file"]["url"])
                print("Expiry Time:", media_data["file"].get("expiry_time"))
            elif media_data["type"] == "external":
                print("External URL:", media_data["external"]["url"])
                
            if media_data.get("caption"):
                print("Caption:", media_data["caption"])
                
            print("===========================\n")
            
        except Exception as e:
            print(f"Error in debug: {e}")

    def handle_media_block(self, block, destination_page_id):
        """Handle copying of media blocks (images and videos) with validation"""
        try:
            block_type = block["type"]
            media_data = block[block_type]
            
            print(f"Processing {block_type} block:", media_data)
            
            # Special handling for Notion-hosted files
            if media_data["type"] == "file":
                media_block = {
                    "object": "block",
                    "type": block_type,
                    block_type: {
                        "type": "file",
                        "file": {
                            "url": media_data["file"]["url"]
                        }
                    }
                }
            else:
                url = media_data["external"]["url"]
                if not self.validate_url(url):
                    print(f"❌ URL validation failed for external {block_type}")
                    return False
                    
                media_block = {
                    "object": "block",
                    "type": block_type,
                    block_type: {
                        "type": "external",
                        "external": {
                            "url": url
                        }
                    }
                }

            # Add caption if it exists
            if media_data.get("caption"):
                media_block[block_type]["caption"] = media_data["caption"]

            # Append the block
            self.notion.blocks.children.append(
                block_id=destination_page_id,
                children=[media_block]
            )
            print(f"✅ Successfully copied {block_type}")
            return True

        except Exception as e:
            print(f"Error copying {block_type}: {e}")
            return False

    def get_unprocessed_campaigns(self):
        """Get campaigns that haven't been processed"""
        try:
            print("Fetching unprocessed campaigns...")
            response = self.notion.databases.query(
                database_id=self.campaign_db_id,
                filter={
                    "property": "Processed",
                    "checkbox": {
                        "equals": False
                    }
                }
            )
            campaigns = response["results"]
            print(f"Found {len(campaigns)} unprocessed campaigns")
            return campaigns
        except Exception as e:
            print(f"Error getting campaigns: {e}")
            return []

    def get_child_pages(self, page_id):
        """Get all child pages of a campaign"""
        try:
            children = self.notion.blocks.children.list(page_id)
            child_pages = [block for block in children["results"] if block["type"] == "child_page"]
            print(f"Found {len(child_pages)} child pages")
            return child_pages
        except Exception as e:
            print(f"Error getting child pages: {e}")
            return []

    def get_page_content(self, page_id):
        """Get all content blocks from a page"""
        try:
            blocks = self.notion.blocks.children.list(page_id)
            return blocks["results"]
        except Exception as e:
            print(f"Error getting page content: {e}")
            return []

    def extract_date_from_content(self, blocks):
        """Extract date from content blocks"""
        try:
            for block in blocks:
                if block["type"] == "heading_1" or block["type"] == "callout":
                    text = ""
                    if block["type"] == "heading_1":
                        text = block["heading_1"]["rich_text"][0]["plain_text"]
                    else:
                        text = block["callout"]["rich_text"][0]["plain_text"]
                    
                    if "Post Date:" in text:
                        date_pattern = r'\d{4}-\d{2}-\d{2}'
                        match = re.search(date_pattern, text)
                        if match:
                            return match.group(0)
                        
                        try:
                            date_text = text.replace("Post Date:", "").strip()
                            parsed_date = datetime.strptime(date_text, "%B %d, %Y")
                            return parsed_date.strftime("%Y-%m-%d")
                        except:
                            pass
            
            return datetime.now().date().isoformat()
        except Exception as e:
            print(f"Error extracting date: {e}")
            return datetime.now().date().isoformat()

    def copy_content_blocks(self, source_blocks, destination_page_id):
        """Copy content blocks to the destination page"""
        try:
            for block in source_blocks:
                # Skip the Post Date block
                if block["type"] in ["heading_1", "callout"]:
                    if "Post Date:" in block.get(block["type"], {}).get("rich_text", [{}])[0].get("plain_text", ""):
                        continue

                block_type = block["type"]
                
                # Handle media blocks
                if block_type in ["image", "video"]:
                    self.debug_media_block(block)
                    if not self.handle_media_block(block, destination_page_id):
                        print(f"Failed to copy {block_type}")
                    continue
                
                elif block_type == "paragraph":
                    text_content = block["paragraph"]["rich_text"]
                    if text_content:
                        self.notion.blocks.children.append(
                            block_id=destination_page_id,
                            children=[{
                                "object": "block",
                                "type": "paragraph",
                                "paragraph": {
                                    "rich_text": text_content
                                }
                            }]
                        )
                
                elif block_type == "heading_1":
                    self.notion.blocks.children.append(
                        block_id=destination_page_id,
                        children=[{
                            "object": "block",
                            "type": "heading_1",
                            "heading_1": {
                                "rich_text": block["heading_1"]["rich_text"]
                            }
                        }]
                    )
                
                elif block_type == "heading_2":
                    self.notion.blocks.children.append(
                        block_id=destination_page_id,
                        children=[{
                            "object": "block",
                            "type": "heading_2",
                            "heading_2": {
                                "rich_text": block["heading_2"]["rich_text"]
                            }
                        }]
                    )
                
                elif block_type == "bulleted_list_item":
                    self.notion.blocks.children.append(
                        block_id=destination_page_id,
                        children=[{
                            "object": "block",
                            "type": "bulleted_list_item",
                            "bulleted_list_item": {
                                "rich_text": block["bulleted_list_item"]["rich_text"]
                            }
                        }]
                    )
                
                elif block_type == "numbered_list_item":
                    self.notion.blocks.children.append(
                        block_id=destination_page_id,
                        children=[{
                            "object": "block",
                            "type": "numbered_list_item",
                            "numbered_list_item": {
                                "rich_text": block["numbered_list_item"]["rich_text"]
                            }
                        }]
                    )

        except Exception as e:
            print(f"Error copying content blocks: {e}")

    def mark_campaign_processed(self, campaign_id):
        """Mark a campaign as processed"""
        try:
            self.notion.pages.update(
                page_id=campaign_id,
                properties={
                    "Processed": {
                        "checkbox": True
                    }
                }
            )
            return True
        except Exception as e:
            print(f"Error marking campaign as processed: {e}")
            return False

    def add_to_content_calendar(self, child_page, campaign):
        """Add a child page to the content calendar with content"""
        try:
            # Get child page title
            page_title = child_page["child_page"]["title"]
            
            # Get content first to extract date
            source_content = self.get_page_content(child_page["id"])
            post_date = self.extract_date_from_content(source_content)
            
            # Create content calendar entry
            new_page = self.notion.pages.create(
                parent={"database_id": self.content_db_id},
                properties={
                    "Name": {
                        "title": [
                            {
                                "text": {
                                    "content": page_title
                                }
                            }
                        ]
                    },
                    "Date": {
                        "date": {
                            "start": post_date
                        }
                    },
                    "Status": {
                        "select": {
                            "name": "Draft"
                        }
                    },
                    "Tags": {
                        "multi_select": []
                    }
                }
            )
            
            # Copy content to new page
            print(f"Copying content from '{page_title}'...")
            self.copy_content_blocks(source_content, new_page["id"])
            
            print(f"✅ Added '{page_title}' to content calendar with content")
            return True
        except Exception as e:
            print(f"Error adding to content calendar: {e}")
            print(f"Error details: {str(e)}")
            return False

    def process_single_campaign(self, campaign_id):
        """Process a single campaign by ID"""
        try:
            campaign = self.notion.pages.retrieve(campaign_id)
            print(f"\nProcessing campaign: {campaign_id}")
            
            # Get child pages
            child_pages = self.get_child_pages(campaign_id)
            
            if not child_pages:
                print("No child pages found")
                self.mark_campaign_processed(campaign_id)
                return

            # Process each child page
            success = True
            for child_page in child_pages:
                if not self.add_to_content_calendar(child_page, campaign):
                    success = False

            # Mark campaign as processed if successful
            if success:
                self.mark_campaign_processed(campaign_id)
                print("✅ Campaign processed successfully")
            else:
                print("⚠️ Some content failed to process")
                
        except Exception as e:
            print(f"Error processing campaign {campaign_id}: {e}")

    def process_campaigns(self):
        """Main processing function"""
        print("\n=== Starting Campaign Processing ===")
        
        # Get campaigns
        campaigns = self.get_unprocessed_campaigns()
        if not campaigns:
            print("No new campaigns to process")
            return

        for campaign in campaigns:
            try:
                campaign_title = campaign["properties"]["Name"]["title"][0]["text"]["content"]
                print(f"\nProcessing campaign: {campaign_title}")
            except:
                print(f"\nProcessing campaign: {campaign['id']}")
            
            # Get child pages
            child_pages = self.get_child_pages(campaign["id"])
            
            if not child_pages:
                print("No child pages found")
                # Mark campaign as processed even if no child pages
                self.mark_campaign_processed(campaign["id"])
                continue

            # Process each child page
            success = True
            for child_page in child_pages:
                if not self.add_to_content_calendar(child_page, campaign):
                    success = False

            # Mark campaign as processed if successful
            if success:
                self.mark_campaign_processed(campaign["id"])
                print("✅ Campaign processed successfully")
            else:
                print("⚠️ Some content failed to process")

def webhook_handler(event, context):
    """Handle Notion webhook events"""
    try:
        # Parse the webhook payload
        body = json.loads(event['body'])
        
        # Check if it's a new campaign
        if body['type'] == 'page_created':
            # Instead of processing immediately, trigger the main Lambda function
            # This avoids timeout issues with the webhook
            lambda_client = boto3.client('lambda')
            
            payload = {
                'campaign_id': body['page']['id'],
                'source': 'webhook'
            }
            
            # Asynchronously invoke the main processing function
            lambda_client.invoke(
                FunctionName=os.environ.get('AWS_LAMBDA_FUNCTION_NAME').replace('webhookHandler', 'processCampaigns'),
                InvocationType='Event',  # async invocation
                Payload=json.dumps(payload)
            )
            
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'Processing triggered successfully',
                    'campaign_id': body['page']['id']
                })
            }
            
        return {
            'statusCode': 200,
            'body': json.dumps({'message': 'Webhook received but no action needed'})
        }
        
    except Exception as e:
        print(f"Error processing webhook: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }

def lambda_handler(event, context):
    """AWS Lambda handler function"""
    try:
        automation = NotionAutomation()
        
        # Check if this is a webhook-triggered execution
        if 'campaign_id' in event:
            # Process single campaign
            automation.process_single_campaign(event['campaign_id'])
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': f'Campaign {event["campaign_id"]} processed successfully',
                    'timestamp': datetime.now().isoformat()
                })
            }
        else:
            # Regular scheduled processing
            automation.process_campaigns()
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'message': 'Scheduled campaign processing completed successfully',
                    'timestamp': datetime.now().isoformat()
                })
            }
            
    except Exception as e:
        print(f"Error in lambda execution: {e}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e),
                'timestamp': datetime.now().isoformat()
            })
        }

# Only run if script is run directly (not through Lambda)
if __name__ == "__main__":
    automation = NotionAutomation()
    automation.process_campaigns()