-- @param category STRING
WITH mock AS (
  SELECT 'Acme Oyster House' AS business_name, 4.0 AS rating, 7568 AS review_count, 15205 AS checkin_count, 'New Orleans' AS city, 'Restaurants and cuisines' AS category
  UNION ALL SELECT 'Oceana Grill', 4.0, 7400, 21542, 'New Orleans', 'Restaurants and cuisines'
  UNION ALL SELECT 'Ruby Slipper', 4.5, 5193, 10209, 'New Orleans', 'Restaurants and cuisines'
  UNION ALL SELECT 'Mother''s Restaurant', 3.5, 5185, 9034, 'New Orleans', 'Restaurants and cuisines'
  UNION ALL SELECT 'Royal House', 4.0, 5070, 28927, 'New Orleans', 'Restaurants and cuisines'
  UNION ALL SELECT 'Commander''s Palace', 4.5, 4876, 7261, 'New Orleans', 'Restaurants and cuisines'
  UNION ALL SELECT 'Cochon', 4.0, 4421, 8503, 'New Orleans', 'Restaurants and cuisines'
  UNION ALL SELECT 'Felix''s Oyster Bar', 4.0, 3966, 7146, 'New Orleans', 'Restaurants and cuisines'
  UNION ALL SELECT 'Gumbo Shop', 4.0, 3902, 9574, 'New Orleans', 'Restaurants and cuisines'
  UNION ALL SELECT 'Cochon Butcher', 4.5, 3837, 8855, 'New Orleans', 'Grocery markets and specialty food'
  UNION ALL SELECT 'Bacchanal Wine', 4.5, 3500, 6200, 'New Orleans', 'Bars, breweries, and nightlife'
  UNION ALL SELECT 'Cafe Du Monde', 4.0, 3200, 12000, 'New Orleans', 'Cafes, bakeries, and sweets'
  UNION ALL SELECT 'Brennan''s', 4.5, 2800, 5100, 'New Orleans', 'Restaurants and cuisines'
  UNION ALL SELECT 'Dat Dog', 3.5, 2100, 4300, 'New Orleans', 'Restaurants and cuisines'
  UNION ALL SELECT 'Jacques-Imo''s', 4.0, 1900, 3200, 'New Orleans', 'Restaurants and cuisines'
  UNION ALL SELECT 'Willie Mae''s', 4.5, 1800, 2900, 'New Orleans', 'Restaurants and cuisines'
  UNION ALL SELECT 'Parkway Tavern', 4.5, 1600, 2500, 'New Orleans', 'Restaurants and cuisines'
  UNION ALL SELECT 'Coop''s Place', 4.0, 1400, 2100, 'New Orleans', 'Restaurants and cuisines'
  UNION ALL SELECT 'Cafe Beignet', 3.5, 1200, 3800, 'New Orleans', 'Cafes, bakeries, and sweets'
  UNION ALL SELECT 'NOLA Brewing', 4.5, 350, 1200, 'New Orleans', 'Bars, breweries, and nightlife'
  UNION ALL SELECT 'Rouses Market', 4.0, 400, 900, 'New Orleans', 'Grocery markets and specialty food'
  UNION ALL SELECT 'Audubon Zoo', 4.5, 1500, 4800, 'New Orleans', 'Arts, culture, and entertainment'
  UNION ALL SELECT 'NOMA', 4.0, 800, 2200, 'New Orleans', 'Arts, culture, and entertainment'
  UNION ALL SELECT 'Frenchmen Books', 4.5, 180, 420, 'New Orleans', 'Retail shopping'
  UNION ALL SELECT 'Aidan Gill', 4.5, 210, 380, 'New Orleans', 'Beauty, spas, and personal care'
)
SELECT business_name, rating, review_count, checkin_count, city
FROM mock
WHERE category = :category
ORDER BY review_count DESC
LIMIT 100