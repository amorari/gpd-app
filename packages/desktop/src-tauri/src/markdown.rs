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
    use super::*;

    #[test]
    fn empty_input_returns_empty_or_just_newline() {
        let result = parse_markdown("");
        // comrak returns an empty string for empty input
        assert!(
            result.is_empty() || result == "\n",
            "expected empty string or bare newline, got: {result:?}"
        );
    }

    #[test]
    fn plain_text_renders_as_paragraph() {
        let result = parse_markdown("hello");
        assert!(
            result.contains("<p>hello</p>"),
            "expected <p>hello</p> in output, got: {result:?}"
        );
    }

    #[test]
    fn external_link_gets_class_and_target() {
        let result = parse_markdown("[text](https://example.com)");
        assert!(
            result.contains("class=\"external-link\""),
            "expected class=\"external-link\" in output, got: {result:?}"
        );
        assert!(
            result.contains("target=\"_blank\""),
            "expected target=\"_blank\" in output, got: {result:?}"
        );
        assert!(
            result.contains("rel=\"noopener noreferrer\""),
            "expected rel=\"noopener noreferrer\" in output, got: {result:?}"
        );
    }

    #[test]
    fn raw_html_is_stripped() {
        let result = parse_markdown("<script>alert(1)</script>");
        assert!(
            !result.contains("<script>"),
            "expected <script> to be stripped (unsafe=false), got: {result:?}"
        );
    }

    #[test]
    fn strikethrough_rendered() {
        let result = parse_markdown("~~text~~");
        assert!(
            result.contains("<del>text</del>") || result.contains("<s>text</s>"),
            "expected <del>text</del> or <s>text</s> in output, got: {result:?}"
        );
    }

    #[test]
    fn task_list_rendered() {
        let result = parse_markdown("- [ ] item");
        assert!(
            result.contains("<input"),
            "expected checkbox <input in output, got: {result:?}"
        );
        assert!(
            result.contains("type=\"checkbox\""),
            "expected type=\"checkbox\" in output, got: {result:?}"
        );
    }
}
