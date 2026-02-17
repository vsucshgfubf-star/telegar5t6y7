import requests
import logging
from config import PIRATESWAP_API, PAGES_TO_SCAN, RESULTS_PER_PAGE

logger = logging.getLogger(__name__)

class PirateSwapParser:
    def __init__(self):
        self.api_url = PIRATESWAP_API
        self.timeout = 10
        self.max_retries = 3
    
    def fetch_inventory(self, page):
        """Fetch inventory page from PirateSwap API"""
        params = {
            'page': page,
            'results': RESULTS_PER_PAGE,
            'orderBy': 'price',
            'sortOrder': 'desc'
        }
        
        for attempt in range(self.max_retries):
            try:
                response = requests.get(
                    self.api_url,
                    params=params,
                    timeout=self.timeout,
                    headers={'User-Agent': 'Mozilla/5.0'}
                )
                response.raise_for_status()
                data = response.json()
                
                if 'data' in data and isinstance(data['data'], list):
                    logger.info(f"Successfully fetched page {page} with {len(data['data'])} items")
                    return data['data']
                else:
                    logger.warning(f"Unexpected API response format on page {page}")
                    return []
                    
            except requests.exceptions.Timeout:
                logger.warning(f"Timeout on page {page}, attempt {attempt + 1}/{self.max_retries}")
            except requests.exceptions.ConnectionError:
                logger.warning(f"Connection error on page {page}, attempt {attempt + 1}/{self.max_retries}")
            except requests.exceptions.HTTPError as e:
                logger.error(f"HTTP error on page {page}: {e}")
                break
            except Exception as e:
                logger.error(f"Error parsing page {page}: {e}")
                break
        
        return []
    
    def get_all_items(self):
        """Fetch items from all pages"""
        all_items = []
        
        for page in range(1, PAGES_TO_SCAN + 1):
            items = self.fetch_inventory(page)
            all_items.extend(items)
        
        logger.info(f"Total items fetched: {len(all_items)}")
        return all_items
