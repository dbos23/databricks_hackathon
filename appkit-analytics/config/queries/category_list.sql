-- Returns distinct top-level categories for New Orleans area businesses (mock)
SELECT 'Restaurants and cuisines' AS category, 1642 AS business_count
UNION ALL SELECT 'Retail shopping', 698
UNION ALL SELECT 'Travel and transportation', 616
UNION ALL SELECT 'Beauty, spas, and personal care', 521
UNION ALL SELECT 'Home and repair services', 444
UNION ALL SELECT 'Bars, breweries, and nightlife', 393
UNION ALL SELECT 'Health and medical', 380
UNION ALL SELECT 'Cafes, bakeries, and sweets', 304
UNION ALL SELECT 'Arts, culture, and entertainment', 256
UNION ALL SELECT 'Grocery markets and specialty food', 203
UNION ALL SELECT 'Fitness and recreation', 180
ORDER BY business_count DESC