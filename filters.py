import logging
import unicodedata
import re

logger = logging.getLogger(__name__)

def normalize(s):
    if not isinstance(s, str):
        s = str(s) if s is not None else ''
    # Unicode NFKD
    s = unicodedata.normalize('NFKD', s)
    # В ASCII (без спецсим волов)
    s = s.encode('ascii', 'ignore').decode('ascii')
    # Убираем спецсимволы и двойные пробелы
    s = re.sub(r'[^a-zA-Z0-9\s]', '', s)
    s = s.lower()
    s = re.sub(r'\s+', ' ', s)
    s = s.strip()
    return s

class ItemFilter:
    @staticmethod
    def check_name_match(user_text, market_hash_name):
        n_user = normalize(user_text)
        n_name = normalize(market_hash_name)
        result = n_user in n_name
        logger.info(f"[FILTER][COMPARE]\nuser = {repr(user_text)} → {repr(n_user)}"
                    f"\nitem = {repr(market_hash_name)} → {repr(n_name)}\nresult = {result}")
        return result

    @staticmethod
    def check_keychain_requirement(charm_required, item_keychains):
        # Безопасно: если нет поля, если None, всегда []!
        keychains = item_keychains or []
        result = True if charm_required == 0 else len(keychains) > 0
        logger.info(
            f"[FILTER][KEYCHAIN] charm_required={charm_required}, found={len(keychains)}, result={result}"
        )
        return result

    @staticmethod
    def filter_items(items, user_searches, db):
        matches = []
        logger.info(f"[FILTER] Starting filter_items: {len(items)} items, {len(user_searches)} searches")

        for item in items:
            try:
                item_id = str(item.get('id'))
                market_hash_name = item.get('marketHashName', '')
                price = item.get('price', 0)
                float_val = item.get('float', 0)
                keychains = item.get('keyChains') or []
                inspect_link = item.get('inspectInGameLink', '')

                # Проверка дубликата в БД
                if db.item_exists(item_id):
                    logger.info(f"[FILTER] Already processed item_id {item_id}, skipping.")
                    continue

                # Ищем среди всех поисков
                match_found = False
                for user_id, skin_name, charm_required in user_searches:
                    logger.info(f"[FILTER] Checking item '{market_hash_name}' (id={item_id}) "
                                f"for user {user_id}, search='{skin_name}', charm={charm_required}")

                    if ItemFilter.check_name_match(skin_name, market_hash_name):
                        if ItemFilter.check_keychain_requirement(charm_required, keychains):
                            logger.info(f"[FILTER] === MATCHED: '{market_hash_name}' for user {user_id}")
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
                            match_found = True
                        else:
                            logger.info("[FILTER] No keychain match")
                    else:
                        logger.info("[FILTER] Name not matched")
                # ТОЛЬКО если кто-то действительно хочет такой предмет — сохраняем в БД!
                if match_found:
                    db.save_item(item_id, market_hash_name, price, float_val, len(keychains), inspect_link)
            except Exception as e:
                logger.error(f"❌ Error filtering item: {e}", exc_info=True)
                continue
        logger.info(f"[FILTER] Total matches found: {len(matches)}")
        return matches
