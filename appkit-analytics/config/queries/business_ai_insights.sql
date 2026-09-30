-- @param business_name STRING
-- @param selected_month STRING
WITH biz_reviews AS (
  SELECT 
    r.full_text,
    r.posted_at
  FROM genieology.gold.reviews_and_tips r
  JOIN genieology.gold.business b ON r.business_id = b.business_id
  WHERE b.business_name = :business_name
    AND (:selected_month = '' OR DATE_FORMAT(r.posted_at, 'yyyy-MM') = :selected_month)
    AND r.full_text IS NOT NULL
)
SELECT 
  COUNT(*) AS total_reviews,
  SUM(CASE WHEN LOWER(full_text) RLIKE '(great|excellent|amazing|best|love|fantastic|delicious|wonderful|friendly|top)' THEN 1 ELSE 0 END) AS pos_signals,
  SUM(CASE WHEN LOWER(full_text) RLIKE '(bad|terrible|slow|rude|dirty|horrible|overpriced|disappointed|worst|poor)' THEN 1 ELSE 0 END) AS neg_signals,
  SUM(CASE WHEN LOWER(full_text) RLIKE '(cocktail|wine|bar|drink|beer|happy hour)' THEN 1 ELSE 0 END) AS count_drinks,
  SUM(CASE WHEN LOWER(full_text) RLIKE '(atmosphere|vibe|ambiance|decor|cozy|intimate|romantic|music)' THEN 1 ELSE 0 END) AS count_vibe,
  SUM(CASE WHEN LOWER(full_text) RLIKE '(service|staff|server|waiter|waitress|hospitality)' THEN 1 ELSE 0 END) AS count_service,
  SUM(CASE WHEN LOWER(full_text) RLIKE '(patio|outdoor|seating|view|terrace)' THEN 1 ELSE 0 END) AS count_patio,
  SUM(CASE WHEN LOWER(full_text) RLIKE '(family|kids|children|group|party)' THEN 1 ELSE 0 END) AS count_family,
  SUM(CASE WHEN LOWER(full_text) RLIKE '(tourist|trip|visit|hotel|vacation|flight|out of town|traveling)' THEN 1 ELSE 0 END) AS count_tourist,
  SUM(CASE WHEN LOWER(full_text) RLIKE '(local|regular|favorite|always|weekly|neighborhood|go-to)' THEN 1 ELSE 0 END) AS count_local,
  SUM(CASE WHEN LOWER(full_text) RLIKE '(business|meeting|client|work|conference|lunch)' THEN 1 ELSE 0 END) AS count_business,
  SUM(CASE WHEN LOWER(full_text) RLIKE '(wait|line|reservation|busy|crowded|long wait)' THEN 1 ELSE 0 END) AS count_wait,
  SUM(CASE WHEN LOWER(full_text) RLIKE '(expensive|price|cost|overpriced|pricy|value)' THEN 1 ELSE 0 END) AS count_price,
  SUM(CASE WHEN LOWER(full_text) RLIKE '(noise|loud|music|noisy)' THEN 1 ELSE 0 END) AS count_noise,
  SUM(CASE WHEN LOWER(full_text) RLIKE '(parking|car|park)' THEN 1 ELSE 0 END) AS count_parking
FROM biz_reviews