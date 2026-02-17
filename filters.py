import logging

logger = logging.getLogger(__name__)

class ItemFilter:
    @staticmethod
    def check_name_match(user_text, market_hash_name):
        result = user_text.lower() in market_hash_name.lower()
        logger.info(
            f"[FILTER] Compare: '{user_text.lower()}' in '{market_hash_name.lower()}': {result}"
        )
        return result

    @staticmethod
    def check_keychain_requirement(charm_required, item_keychains):
        if charm_required == 0:
            logger.info(f"[FILTER] Keychains not required (charm_required=0), passed")
            return True
        result = len(item_keychains) > 0
        logger.info(
            f"[FILTER] Keychains required (charm_required=1), found {len(item_keychains)}: {result}"
        )
        return result

    @staticmethod
    def filter_items(items, user_searches, db):
        matches = []
        logger.info(f"[FILTER] Starting filter_items: {len(items)} items, {len(user_searches)} searches")

        for item in items:
            try:
                item_id = item.get('id')
                market_hash_name = item.get('marketHashName', '')
                price = item.get('price', 0)
                float_val = item.get('float', 0)
                keychains = item.get('keyChains', [])
                inspect_link = item.get('inspectInGameLink', '')

                if db.item_exists(item_id):
                    logger.info(f"[FILTER] Already processed item_id {item_id}, skipping.")
                    continue

                db.save_item(item_id, market_hash_name, price, float_val, len(keychains), inspect_link)

                for user_id, skin_name, charm_required in user_searches:
                    logger.info(
                        f"[FILTER] Checking item '{market_hash_name}' for user {user_id}, search='{skin_name}', charm_required={charm_required}"
                    )
                    if ItemFilter.check_name_match(skin_name, market_hash_name):
                        if ItemFilter.check_keychain_requirement(charm_required, keychains):
                            logger.info(f"[FILTER] === MATCHED: item '{market_hash_name}' for user {user_id}")
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
                        else:
                            logger.info(
                                f"[FILTER] Keychain requirement not satisfied for '{market_hash_name}'"
                            )
                    else:
                        logger.info(
                            f"[FILTER] Name '{skin_name}' NOT found in '{market_hash_name}'"
                        )
            except Exception as e:
                logger.error(f"❌ Error filtering item: {e}")
                continue

        logger.info(f"[FILTER] Total matches found: {len(matches)}")
        return matches
