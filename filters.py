import logging

logger = logging.getLogger(__name__)

class ItemFilter:
    @staticmethod
    def check_name_match(user_text, market_hash_name):
        """Check if user text matches item name"""
        return user_text.lower() in market_hash_name.lower()
    
    @staticmethod
    def check_keychain_requirement(charm_required, item_keychains):
        """Check if item meets keychain requirement"""
        if charm_required == 0:
            return True
        return len(item_keychains) > 0
    
    @staticmethod
    def filter_items(items, user_searches, db):
        """
        Filter items based on user searches
        Returns list of matching items with user info
        """
        matches = []
        
        for item in items:
            try:
                item_id = item.get('id')
                market_hash_name = item.get('marketHashName', '')
                price = item.get('price', 0)
                float_val = item.get('float', 0)
                keychains = item.get('keyChains', [])
                inspect_link = item.get('inspectInGameLink', '')
                
                # Check if item already processed
                if db.item_exists(item_id):
                    continue
                
                # Save item to avoid reprocessing
                db.save_item(item_id, market_hash_name, price, float_val, len(keychains), inspect_link)
                
                # Check against all user searches
                for user_id, skin_name, charm_required in user_searches:
                    if ItemFilter.check_name_match(skin_name, market_hash_name):
                        if ItemFilter.check_keychain_requirement(charm_required, keychains):
                            matches.append({
                                'user_id': user_id,
                                'item_id': item_id,
                                'market_hash_name': market_hash_name,
                                'price': price,
                                'float': float_val,
                                'has_keychains': len(keychains) > 0,
                                'keychains': keychains,
                                'inspect_link': inspect_link
                            })
            except Exception as e:
                logger.error(f"❌ Error filtering item: {e}")
                continue
        
        return matches
