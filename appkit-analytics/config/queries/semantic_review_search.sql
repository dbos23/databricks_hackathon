-- @param query_text STRING
-- @param business_name STRING
-- @param selected_month STRING
WITH vector_matches AS (
  SELECT text_id, search_score
  FROM vector_search(
    index => 'genieology.gold.yelp_index',
    query_text => COALESCE(:query_text, 'service and atmosphere'),
    num_results => 100
  )
),
hybrid_reviews AS (
  SELECT 
    r.text_id,
    r.full_text,
    r.posted_at,
    COALESCE(v.search_score, 0) AS search_score,
    CASE WHEN v.text_id IS NOT NULL THEN 1 ELSE 0 END AS is_vector_match
  FROM genieology.gold.reviews_and_tips r
  JOIN genieology.gold.business b ON r.business_id = b.business_id
  LEFT JOIN vector_matches v ON CAST(r.text_id AS STRING) = CAST(v.text_id AS STRING)
  WHERE b.business_name = :business_name
    AND (:selected_month = '' OR DATE_FORMAT(r.posted_at, 'yyyy-MM') = :selected_month)
    AND (
      v.text_id IS NOT NULL 
      OR LOWER(r.full_text) LIKE LOWER(CONCAT('%', REPLACE(:query_text, ' ', '%'), '%'))
      OR :query_text = ''
    )
)
SELECT 
  text_id,
  full_text,
  posted_at,
  search_score AS score
FROM hybrid_reviews
ORDER BY is_vector_match DESC, score DESC, posted_at DESC
LIMIT 12