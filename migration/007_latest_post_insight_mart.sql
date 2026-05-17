-- Pre-deduplicated analytics mart for dashboard reads.
--
-- The live dashboard repeatedly needs the latest row per platform/source
-- identity. Doing DISTINCT ON across analysis.post_insight on every
-- kpis/posts/platforms request is expensive once a campaign has hundreds of
-- thousands of mentions, so we materialize the latest business-grade slice and
-- refresh it in the API process. Raw low-relevance rows stay in post_insight.

CREATE MATERIALIZED VIEW IF NOT EXISTS analysis.latest_post_insight AS
SELECT DISTINCT ON (
  COALESCE(NULLIF(UPPER(pi.platform), ''), 'UNKNOWN'),
  COALESCE(
    NULLIF(pi.source_id, ''),
    NULLIF(pi.uap_metadata->>'post_id', ''),
    NULLIF(pi.uap_metadata->>'comment_id', ''),
    NULLIF(pi.uap_metadata->>'video_id', ''),
    NULLIF(pi.uap_metadata->>'url', ''),
    pi.id::text
  )
)
  pi.*
FROM analysis.post_insight pi
WHERE (
  (
    pi.business_relevance_score >= 0.45
    AND (
      COALESCE(pi.uap_metadata #>> '{platform_meta,smap,source_kind}', '') IN ('focused_page', 'focused_profile')
      OR (
        (
          (
            COALESCE(pi.uap_metadata #>> '{crawl_keyword}', '') <> ''
            AND COALESCE(pi.content, '') ~* '(ahamove|grab|lalamove|be|xanh sm|giao hàng|shipper|tài xế|đơn hàng|đặt xe|vận chuyển|thu hộ|cod|tanca|hrm|crm|nhân sự|chấm công|bảng lương|tiền lương|sales|marketing|chiến dịch|thương hiệu|dịch vụ|khách hàng|tổng đài|hỗ trợ)'
          )
          OR (
            COALESCE(array_length(pi.keywords, 1), 0) > 0
            AND COALESCE(pi.content, '') ~* '(ahamove|grab|lalamove|be|xanh sm|giao hàng|shipper|tài xế|đơn hàng|đặt xe|vận chuyển|thu hộ|cod|tanca|hrm|crm|nhân sự|chấm công|bảng lương|tiền lương|sales|marketing|chiến dịch|thương hiệu|dịch vụ|khách hàng|tổng đài|hỗ trợ)'
          )
          OR (
            (
              COALESCE(pi.uap_metadata->>'url', '') <> ''
              OR COALESCE(pi.uap_metadata->>'post_url', '') <> ''
              OR COALESCE(pi.uap_metadata->>'original_url', '') <> ''
              OR COALESCE(pi.uap_metadata->>'source_url', '') <> ''
              OR COALESCE(pi.uap_metadata->>'web_url', '') <> ''
              OR COALESCE(pi.uap_metadata->>'parent_post_url', '') <> ''
              OR COALESCE(pi.uap_metadata->>'comment_url', '') <> ''
              OR COALESCE(pi.uap_metadata->>'share_url', '') <> ''
              OR COALESCE(pi.uap_metadata->>'permalink_url', '') <> ''
              OR COALESCE(pi.uap_metadata #>> '{platform_meta,youtube,parent_url}', '') <> ''
              OR COALESCE(pi.uap_metadata #>> '{platform_meta,youtube,video_url}', '') <> ''
              OR COALESCE(pi.uap_metadata #>> '{platform_meta,tiktok,video_url}', '') <> ''
              OR COALESCE(pi.uap_metadata #>> '{platform_meta,facebook,post_url}', '') <> ''
              OR COALESCE(pi.uap_metadata #>> '{platform_meta,facebook,permalink_url}', '') <> ''
            )
            AND (
              COALESCE(pi.content, '') ~* '(ahamove|grab|lalamove|be|xanh sm|giao hàng|shipper|tài xế|đơn hàng|đặt xe|vận chuyển|thu hộ|cod|tanca|hrm|crm|nhân sự|chấm công|bảng lương|tiền lương|sales|marketing|chiến dịch|thương hiệu|dịch vụ|khách hàng|tổng đài|hỗ trợ)'
              OR pi.business_relevance_score >= 0.72
            )
          )
        )
        AND (
          NOT COALESCE(pi.content, '') ~* '(youtube\.com/shopcollection|bộ đồ nghề|zalo|chuyên bán|menu trái cây|bánh cuốn|serum|cọ gấu|hàng có sẵn|hàng_có_sẵn|định danh chủ|cà mau.*đăng ký|đăng ký.*cà mau|(^|[^0-9])0[0-9]{8,10}([^0-9]|$))'
          AND (
            NOT COALESCE(pi.content, '') ~* '(zalo|inbox|(^|[^[:alnum:]_])ib([^[:alnum:]_]|$)|chốt đơn|menu|shop|có sẵn|hàng có sẵn|hàng_có_sẵn|đồng giá|sỉ|lẻ|mỹ phẩm|serum|son|trái cây|bánh|chậu|cây|lồng đèn|túi|áo khoác|ship toàn quốc|ship từ|phí ship|ngoại ô xa phí|bao check|bán hàng|cần ra đi|em mời khách|(^|[^[:alnum:]_])[0-9]{2,4}k([^[:alnum:]_]|$))'
            OR COALESCE(pi.content, '') ~* '(trải nghiệm|review|đánh giá|phản hồi|phàn nàn|khiếu nại|bức xúc|hài lòng|không hài lòng|lỗi|tệ|ổn|chậm|trễ|delay|hủy|huỷ|hoàn tiền|refund|đối soát|đơn hàng|đơn|book|đặt|app|ứng dụng|tài xế|shipper|driver|đối tác|chạy|thu nhập|kiếm|lương|phạt|thưởng|đăng ký|hỗ trợ|tổng đài|khách hàng|cước|giá cước|cod|thu hộ|giao hàng|vận chuyển|dịch vụ)'
          )
        )
      )
    )
  )
  OR COALESCE(pi.uap_metadata #>> '{platform_meta,smap,source_kind}', '') IN ('focused_page', 'focused_profile')
)
ORDER BY
  COALESCE(NULLIF(UPPER(pi.platform), ''), 'UNKNOWN'),
  COALESCE(
    NULLIF(pi.source_id, ''),
    NULLIF(pi.uap_metadata->>'post_id', ''),
    NULLIF(pi.uap_metadata->>'comment_id', ''),
    NULLIF(pi.uap_metadata->>'video_id', ''),
    NULLIF(pi.uap_metadata->>'url', ''),
    pi.id::text
  ),
  COALESCE(pi.updated_at, pi.analyzed_at, pi.ingested_at, pi.created_at) DESC NULLS LAST,
  pi.created_at DESC NULLS LAST,
  pi.id DESC;

CREATE UNIQUE INDEX IF NOT EXISTS idx_latest_post_insight_id
  ON analysis.latest_post_insight (id);

CREATE INDEX IF NOT EXISTS idx_latest_post_insight_project_relevance
  ON analysis.latest_post_insight (project_id, business_relevance_score);

CREATE INDEX IF NOT EXISTS idx_latest_post_insight_project_engagement
  ON analysis.latest_post_insight (
    project_id,
    engagement_score DESC NULLS LAST,
    content_created_at DESC NULLS LAST
  );

CREATE INDEX IF NOT EXISTS idx_latest_post_insight_project_time
  ON analysis.latest_post_insight (project_id, content_created_at DESC NULLS LAST);

CREATE INDEX IF NOT EXISTS idx_latest_post_insight_project_platform_sentiment
  ON analysis.latest_post_insight (
    project_id,
    (COALESCE(NULLIF(UPPER(platform), ''), 'UNKNOWN')),
    (UPPER(COALESCE(overall_sentiment, '')))
  );

CREATE INDEX IF NOT EXISTS idx_latest_post_insight_project_source_kind
  ON analysis.latest_post_insight (
    project_id,
    (COALESCE(uap_metadata #>> '{platform_meta,smap,source_kind}', ''))
  );

CREATE INDEX IF NOT EXISTS idx_latest_post_insight_keywords
  ON analysis.latest_post_insight USING GIN (keywords);

GRANT SELECT ON analysis.latest_post_insight TO analysis_prod;
GRANT TEMPORARY ON DATABASE smap TO analysis_master;
GRANT TEMPORARY ON DATABASE smap TO analysis_prod;

CREATE OR REPLACE FUNCTION analysis.refresh_latest_post_insight()
RETURNS void
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = analysis, public
AS $$
BEGIN
  REFRESH MATERIALIZED VIEW CONCURRENTLY analysis.latest_post_insight;
END;
$$;

GRANT EXECUTE ON FUNCTION analysis.refresh_latest_post_insight() TO analysis_prod;
