SELECT 
  business_name,
  rating,
  review_count
FROM genieology.gold.business
ORDER BY review_count DESC
LIMIT 100