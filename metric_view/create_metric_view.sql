create or replace view genieology.gold.business_metric_view
comment 'Metric view for the Yelp businesses, reviews, and tips'
with metrics
language yaml
as
$$
    version: 1.1
    source: genieology.gold.reviews_and_tips

    joins:
      - name: business
        source: genieology.gold.business
        'on': source.business_id = business.business_id
        rely:
          at_most_one_match: false

    fields:
      - name: business ID
        expr: business.business_id
        comment: 'The ID of the business on Yelp'

      - name: business name
        expr: business.business_name
        comment: 'The nanme of the business'

      - name: category
        expr: business.category
        comment: 'The category to which the business belongs (e.g. restaurants, retail, etc.)'

      - name: city
        expr: business.city
        comment: 'The city where the business is located'

      - name: state
        expr: business.state
        comment: 'The state where the business is located'

      - name: address
        expr: business.address
        comment: 'The street address of the business'

      - name: postal code
        expr: business.postal_code
        comment: 'The postal code of the business'

      - name: latitude
        expr: business.latitude
        comment: 'The latitude at which the business is located'

      - name: longitude
        expr: business.longitude
        comment: 'The longitude at which the business is located'

      - name: review count
        expr: business.review_count
        comment: 'The number of Yelp reviews a business has received'

      - name: rating
        expr: business.rating
        comment: 'The Yelp rating (out of 5 stars) for the business'

      - name: first checkin
        expr: business.first_checkin
        comment: 'The first date on which a Yelp user has checked in at the business'

      - name: latest checkin
        expr: business.latest_checkin
        comment: 'The latest date on which a Yelp user has checked in at the business'

      - name: checkin count
        expr: business.checkin_count
        comment: 'The number of times a Yelp user has checked in at the business'

      - name: post type
        expr: source.type
        comment: 'The type of Yelp interaction that has been made about the business. Either reivew or tip. Tips are short comments while reviews are longer evaluations of the business'

      - name: posted date
        expr: source.posted_at
        comment: 'The date on which the review/tip was posted on Yelp'

      - name: full text
        expr: source.full_text
        comment: 'The full text of the review or tip that was posted on Yelp'
$$;