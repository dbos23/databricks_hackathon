-- @param business_name STRING
SELECT *
FROM genieology.gold.business
WHERE business_name = :business_name
LIMIT 1