"""
Tamil transliteration utility for PDF rendering.
Converts Tamil Unicode script to Tamil romanization (Latin characters).
"""

# Tamil to Latin Romanization mapping
TAMIL_TO_LATIN = {
    # Vowels (உயிரெழுத்து)
    'அ': 'a',
    'ஆ': 'aa',
    'இ': 'i',
    'ஈ': 'ee',
    'உ': 'u',
    'ஊ': 'uu',
    'எ': 'e',
    'ஏ': 'ai',
    'ஐ': 'ai',
    'ஒ': 'o',
    'ஓ': 'o',
    'ஔ': 'au',

    # Consonants (மெய்யெழுத்து)
    'க': 'ka',
    'ங': 'nga',
    'ச': 'cha',
    'ஞ': 'nja',
    'ட': 'ta',
    'ண': 'na',
    'த': 'tha',
    'ந': 'na',
    'ப': 'pa',
    'ம': 'ma',
    'ய': 'ya',
    'ர': 'ra',
    'ல': 'la',
    'வ': 'va',
    'ழ': 'zha',
    'ள': 'la',
    'ற': 'ra',
    'ன': 'na',

    # Consonant-Vowel combinations (உயிர்मெய்)
    'கா': 'ka',
    'கி': 'ki',
    'கீ': 'kee',
    'கு': 'ku',
    'கூ': 'koo',
    'கெ': 'ke',
    'கே': 'ke',
    'கை': 'kai',
    'கொ': 'ko',
    'கோ': 'ko',
    'கௌ': 'kau',

    'சா': 'cha',
    'சி': 'chi',
    'சீ': 'chee',
    'சு': 'chu',
    'சூ': 'choo',
    'செ': 'che',
    'சே': 'che',
    'சை': 'chai',
    'சொ': 'cho',
    'சோ': 'cho',

    'தா': 'tha',
    'தி': 'thi',
    'தீ': 'thee',
    'து': 'thu',
    'தூ': 'thoo',
    'தெ': 'the',
    'தே': 'the',
    'தை': 'thai',
    'தொ': 'tho',
    'தோ': 'tho',

    'பா': 'pa',
    'பி': 'pi',
    'பீ': 'pee',
    'பு': 'pu',
    'பூ': 'poo',
    'பெ': 'pe',
    'பே': 'pe',
    'பை': 'pai',
    'பொ': 'po',
    'போ': 'po',

    'மா': 'ma',
    'மி': 'mi',
    'மீ': 'mee',
    'மு': 'mu',
    'மூ': 'moo',
    'மெ': 'me',
    'மே': 'me',
    'மை': 'mai',
    'மொ': 'mo',
    'மோ': 'mo',

    'யா': 'ya',
    'யி': 'yi',
    'யூ': 'yoo',

    'ரா': 'ra',
    'രി': 'ri',
    'रू': 'roo',

    'லா': 'la',
    'லி': 'li',
    'லீ': 'lee',
    'லு': 'lu',
    'லூ': 'loo',

    'வா': 'va',
    'வி': 'vi',
    'வீ': 'vee',
    'வு': 'vu',
    'வூ': 'voo',
    'வெ': 've',
    'வே': 've',

    'ழா': 'zha',
    'ழி': 'zhi',

    'ணா': 'na',
    'ணி': 'ni',

    'நா': 'na',
    'நி': 'ni',

    # Additional combinations
    'கடன்': 'kadan',
    'கடை': 'kadai',
    'திட்ட': 'thittan',
    'விவர': 'vivara',
    'ரசीது': 'rasidu',
    'தொகை': 'thogai',
    'வாடிக': 'vaadika',
    'கையாளர': 'kaaiyaalar',
    'கட்ட': 'katta',
    'மொத்த': 'mothan',
    'செலுத': 'selutha',
    'முதன': 'muthan',
    'நோக்க': 'nokka',
    'தற்கால': 'tharkkala',
    'கீழ்': 'keeizh',
    'பாதுகாப்': 'paathugaap',
    'மீட்ட': 'meetta',
    'எடுப்': 'edupp',
    'நேர்': 'neer',
    'வைப்': 'vaaip',
    'சேகரிப்': 'saegarip',
    'சான்': 'chaan',
    'அறிக்கை': 'arikkai',
}

def transliterate_tamil(text):
    """
    Convert Tamil Unicode script to Tamil romanization.
    Falls back to keeping original text if no match found.
    
    Args:
        text (str): Text potentially containing Tamil characters
        
    Returns:
        str: Transliterated text with Latin characters
    """
    if not text:
        return text
    
    result = []
    i = 0
    while i < len(text):
        # Try longest match first (2 characters)
        if i + 1 < len(text):
            two_char = text[i:i+2]
            if two_char in TAMIL_TO_LATIN:
                result.append(TAMIL_TO_LATIN[two_char])
                i += 2
                continue
        
        # Try single character match
        char = text[i]
        if char in TAMIL_TO_LATIN:
            result.append(TAMIL_TO_LATIN[char])
        else:
            result.append(char)  # Keep non-Tamil characters as-is
        i += 1
    
    return ''.join(result)


# Common Tamil terms used in receipts - transliterated versions
TAMIL_TRANSLATIONS = {
    # Receipt terms
    'rasidu': 'Rasidu',  # Receipt
    'kataan': 'Kataan',  # Payment
    'tholkai': 'Tholkai',  # Amount
    'vadi': 'Vadi',  # Interest
    'nila': 'Nila',  # Status
    'selutha': 'Selutha',  # Paid
    'mothham': 'Mothham',  # Total
    'mithamaulla': 'Mithamaulla',  # Remaining
    
    # Person terms
    'vaadikayalalar': 'Vaadikayalalar',  # Customer
    'katavan': 'Katavan',  # Borrower
    'kaiyozhipu': 'Kaiyozhipu',  # Signature
    
    # Common words
    'neram': 'Neram',  # Time
    'pathu': 'Pathu',  # Kept/Pledged
    'thandham': 'Thandham',  # Items
}
