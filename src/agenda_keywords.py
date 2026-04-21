"""
Broad Turkish political agenda keywords (2023-2026 focus).
Used to improve recall in large-scale political search.
"""

AGENDA_2023_2026_KEYWORDS: list[str] = [
    # Elections / institutions
    "2023 seçimleri", "2024 yerel seçim", "erken seçim", "sandık güvenliği",
    "seçim güvenliği", "ysk", "yüksek seçim kurulu", "oy sayımı",
    "itiraz süreci", "seçim tekrarı", "cumhurbaşkanlığı seçimi", "milletvekili seçimi",
    "belediye seçimi", "ankara büyükşehir", "istanbul büyükşehir", "ibb",
    "meclis", "tbmm", "genel kurul", "komisyon", "kanun teklifi", "soru önergesi",
    "araştırma önergesi", "torba yasa", "anayasa", "anayasa değişikliği", "yeni anayasa",
    "sivil anayasa", "anayasanın ilk 4 maddesi", "ilk dört madde",
    "türkiye yüzyılı", "vesayetçi anayasa",
    "güçlendirilmiş parlamenter sistem", "cumhurbaşkanlığı hükümet sistemi",
    "referandum", "ittifak", "cumhur ittifakı", "millet ittifakı",

    # Parties / actors
    "akp", "ak parti", "chp", "mhp", "dem parti", "hdp", "iyi parti",
    "yeniden refah", "hüda par", "tip", "deva", "gelecek partisi",
    "saadet partisi", "demokrat parti", "anahtar parti",
    "erdoğan", "recep tayyip erdoğan", "özgür özel", "kılıçdaroğlu", "bahçeli",
    "müsavat dervişoğlu", "tuncer bakırhan", "tülay hatimoğulları",
    "ekrem imamoğlu", "mansur yavaş", "ali yerlikaya", "mehmet şimşek",
    "hakan fidan", "numan kurtulmuş", "akın gürlek", "can atalay",
    "ümit özdağ", "fatih erbakan",

    # Public agenda / judicial-political themes
    "çözüm süreci", "terörsüz türkiye", "terörle mücadele", "kayyum",
    "dokunulmazlık", "açılım süreci", "demokratikleşme", "yargı bağımsızlığı",
    "siyasi operasyon", "siyasi dava", "iddianame", "gözaltı", "tutuklama",
    "tahliye", "hak ihlali", "anayasa mahkemesi", "hsk", "hsk seçimleri",
    "ağır ceza", "savcılık", "hukuk devleti", "adalet reformu", "imamoğlu davası",
    "sinan ateş davası", "gezi davası", "aym kararı",

    # Protest / social movement
    "protesto", "miting", "yürüyüş", "boykot", "saraçhane", "üniversite protestosu",
    "öğrenci eylemi", "polis müdahalesi", "biber gazı", "tazyikli su",
    "ifade özgürlüğü", "basın özgürlüğü", "toplantı ve gösteri", "sendika", "grev",

    # Economy / social policy
    "enflasyon", "hayat pahalılığı", "asgari ücret", "emekli maaşı", "memur zammı",
    "vergi paketi", "kira artışı", "konut krizi", "işsizlik", "genç işsizliği",
    "merkez bankası", "faiz kararı", "kur korumalı mevduat", "bütçe açığı",
    "kamuda tasarruf", "tasarruf paketi", "gelir dağılımı", "gelir adaleti",
    "dar gelirli", "çiftçi destek", "tarım politikası", "enerji zammı",

    # Security / foreign policy
    "suriye politikası", "ırak operasyonu", "nato", "avrupa birliği", "ab süreci",
    "gazze", "israil", "filistin", "ukrayna", "rusya", "dış politika", "mavi vatan",

    # 2025 protest wave specific
    "diploma iptali", "kent uzlaşısı", "cumhurbaşkanı adayı", "31 mart",
    "belediye başkanı tutuklandı", "ibb soruşturması", "terör suçlaması",
    "hukuk dışı", "siyasi yargı",

    # High-frequency discourse tokens
    "iktidar", "muhalefet", "milli irade", "demokrasi", "özgürlük",
    "adalet", "laiklik", "eşit yurttaşlık", "sosyal devlet", "kamusal kaynak",
]
