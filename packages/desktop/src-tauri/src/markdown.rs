use comrak::{
    Arena, Options, create_formatter, html::ChildRendering, nodes::NodeValue, parse_document,
};
use std::fmt::Write;

create_formatter!(ExternalLinkFormatter, {
    NodeValue::Link(ref nl) => |context, node, entering| {
        let skip = context.options.parse.relaxed_autolinks
            && node.parent().is_some_and(|p| comrak::node_matches!(p, NodeValue::Link(..)));
        if skip {
            return Ok(ChildRendering::HTML);
        }

        if entering {
            context.write_str("<a")?;
            comrak::html::render_sourcepos(context, node)?;

            context.write_str(" href=\"")?;
            let url = &nl.url;
            if !comrak::html::dangerous_url(url) {
                if let Some(rewriter) = &context.options.extension.link_url_rewriter {
                    context.escape_href(&rewriter.to_html(url))?;
                } else {
                    context.escape_href(url)?;
                }
            }
            context.write_str("\"")?;

            if !nl.title.is_empty() {
                context.write_str(" title=\"")?;
                context.escape(&nl.title)?;
                context.write_str("\"")?;
            }

            context.write_str(
                " class=\"external-link\" target=\"_blank\" rel=\"noopener noreferrer\">",
            )?;
        } else {
            context.write_str("</a>")?;
        }
    },
});

pub fn parse_markdown(input: &str) -> String {
    let mut options = Options::default();
    options.extension.strikethrough = true;
    options.extension.table = true;
    options.extension.tasklist = true;
    options.extension.autolink = true;
    options.render.r#unsafe = false;

    let arena = Arena::new();
    let doc = parse_document(&arena, input, &options);
    let mut html = String::new();
    ExternalLinkFormatter::format_document(doc, &options, &mut html).unwrap_or_default();
    html
}

#[tauri::command]
#[specta::specta]
pub async fn parse_markdown_command(markdown: String) -> Result<String, String> {
    Ok(parse_markdown(&markdown))
}

#[cfg(test)]
mod tests {
    use super::parse_markdown;

    // -- link decoration + href preservation --

    #[test]
    fn safe_https_href_is_preserved_and_decorated() {
        let out = parse_markdown("[click](https://example.com)");
        assert!(
            out.contains(r#"href="https://example.com""#),
            "expected https href preserved; got: {out}"
        );
        assert!(out.contains(r#"class="external-link""#), "missing class; got: {out}");
        assert!(out.contains(r#"target="_blank""#), "missing target; got: {out}");
        assert!(
            out.contains(r#"rel="noopener noreferrer""#),
            "missing rel; got: {out}"
        );
    }

    // -- dangerous URL blanking (comrak::html::dangerous_url) --
    // Regression lock for the security posture enforced at markdown.rs:20.
    // Removing or inverting that check must break every test below.

    #[test]
    fn javascript_url_is_blanked() {
        let out = parse_markdown("[xss](javascript:alert(1))");
        assert!(
            !out.contains("javascript:"),
            "javascript: leaked into output: {out}"
        );
        assert!(out.contains(r#"href="""#), "expected empty href; got: {out}");
    }

    #[test]
    fn vbscript_url_is_blanked() {
        let out = parse_markdown("[xss](vbscript:msgbox)");
        assert!(!out.contains("vbscript:"), "vbscript: leaked: {out}");
        assert!(out.contains(r#"href="""#), "expected empty href; got: {out}");
    }

    #[test]
    fn file_url_is_blanked() {
        let out = parse_markdown("[etc](file:///etc/passwd)");
        assert!(!out.contains("file:///"), "file:/// leaked: {out}");
        assert!(out.contains(r#"href="""#), "expected empty href; got: {out}");
    }

    #[test]
    fn data_texthtml_url_is_blanked() {
        let out = parse_markdown("[xss](data:text/html,<script>alert(1)</script>)");
        assert!(
            !out.contains("data:text/html"),
            "data:text/html leaked: {out}"
        );
        assert!(!out.contains("<script>"), "<script> leaked: {out}");
    }

    // -- data:image allowlist (comrak permits data:image/{png,gif,jpeg,webp}) --

    #[test]
    fn data_image_png_is_preserved() {
        let tiny_png = "data:image/png;base64,iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNkYAAAAAYAAjCB0C8AAAAASUVORK5CYII=";
        let md = format!("![tiny]({tiny_png})");
        let out = parse_markdown(&md);
        assert!(
            out.contains("data:image/png;base64,"),
            "data:image/png allowlist broken; got: {out}"
        );
    }

    // -- raw HTML handling (render.unsafe = false) --
    // comrak 0.50 replaces raw HTML with "<!-- raw HTML omitted -->" rather
    // than escaping or stripping. Lock that contract explicitly so a flip
    // to unsafe=true surfaces immediately.

    #[test]
    fn raw_html_script_not_passed_through() {
        let out = parse_markdown("before\n\n<script>alert(1)</script>\n\nafter");
        assert!(!out.contains("<script>"), "<script> leaked: {out}");
        assert!(!out.contains("alert(1)"), "script body leaked: {out}");
        assert!(
            out.contains("<!-- raw HTML omitted -->"),
            "expected comrak omission comment; got: {out}"
        );
    }

    #[test]
    fn raw_html_iframe_not_passed_through() {
        let out = parse_markdown("<iframe src=\"https://evil.com\"></iframe>");
        assert!(!out.contains("<iframe"), "<iframe leaked: {out}");
        assert!(
            out.contains("<!-- raw HTML omitted -->"),
            "expected omission comment; got: {out}"
        );
    }

    #[test]
    fn raw_html_img_onerror_not_passed_through() {
        let out = parse_markdown("text <img src=x onerror=\"alert(1)\"> more");
        assert!(!out.contains("onerror"), "onerror leaked: {out}");
    }

    // -- autolink extension (enabled at parse_markdown options) --

    #[test]
    fn bare_url_is_autolinked_and_decorated() {
        let out = parse_markdown("visit https://example.com now");
        assert!(
            out.contains(r#"href="https://example.com""#),
            "autolink href missing; got: {out}"
        );
        assert!(
            out.contains(r#"class="external-link""#),
            "autolink missing external-link decoration; got: {out}"
        );
    }
}
