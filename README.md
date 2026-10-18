# AI or Reality? Can We Tell the Difference?

A 60-minute lecture by Prof. Dr. Christoph Weisser (Hochschule Bielefeld, HSBI). Students first try to tell real images and quotes from AI-generated ones. They then learn how large language models write: next-token prediction, tokens, training versus inference, and why fluent text can still be false. In the second half, a Streamlit app is built live with Claude Code. It generates labelled health misinformation and has a small and a large model check each claim against WHO evidence.

> **Classroom exercise material.** The app writes deliberately false health claims for teaching. They are not health advice. **Smoking is harmful** ([WHO](https://www.who.int/news-room/fact-sheets/detail/tobacco)).

## What's here

- `lecture-slides.pdf`: the slides. `lecture-slides-with-notes.pdf` adds the presenter notes, and `slides-latex/` holds the LaTeX source.
- `prompts/`: the two prompts pasted into Claude Code during the live build
- `fallback/`: tested versions of the app, with setup steps in each folder's README
- `docs/`: runbook and validation notes

## License

MIT (see [LICENSE](LICENSE)), except the third-party quiz images, which keep their own licences, and the presenter photograph, which is not licensed for reuse.
