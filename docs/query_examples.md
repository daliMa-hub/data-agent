# Query Examples

This document lists example natural-language questions and the expected grounding behavior.

## Example 1: Regional Sales

```text
统计华北地区的销售总额
```

Expected grounding:

- Metric: `GMV`
- Measure column: `fact_order.order_amount`
- Region value: `dim_region.region_name = 华北`
- Join path: `fact_order.region_id -> dim_region.region_id`

Expected SQL pattern:

```sql
SELECT SUM(fact_order.order_amount) AS gmv
FROM fact_order
JOIN dim_region ON fact_order.region_id = dim_region.region_id
WHERE dim_region.region_name = '华北';
```

## Example 2: Category Sales Ranking

```text
各品类的销售额排名
```

Expected grounding:

- Metric: `GMV`
- Measure column: `fact_order.order_amount`
- Product dimension: `dim_product.category`
- Join path: `fact_order.product_id -> dim_product.product_id`

Expected SQL pattern:

```sql
SELECT dim_product.category, SUM(fact_order.order_amount) AS gmv
FROM fact_order
JOIN dim_product ON fact_order.product_id = dim_product.product_id
GROUP BY dim_product.category
ORDER BY gmv DESC;
```

## Example 3: Member-Level Average Order Value

```text
不同会员等级的平均订单金额
```

Expected grounding:

- Metric: `AOV`
- Customer dimension: `dim_customer.member_level`
- Join path: `fact_order.customer_id -> dim_customer.customer_id`

Expected SQL pattern:

```sql
SELECT dim_customer.member_level, AVG(fact_order.order_amount) AS aov
FROM fact_order
JOIN dim_customer ON fact_order.customer_id = dim_customer.customer_id
GROUP BY dim_customer.member_level;
```

## Notes

The actual generated SQL may vary depending on the LLM and retrieved context. The important point is not that the SQL text is identical, but that the model grounds the question to the correct metric, fields, values, and join path.
