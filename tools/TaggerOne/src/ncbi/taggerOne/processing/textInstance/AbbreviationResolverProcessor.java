package ncbi.taggerOne.processing.textInstance;

import ncbi.taggerOne.types.MentionName;
import ncbi.taggerOne.types.Segment;
import ncbi.taggerOne.types.TextInstance;
import ncbi.taggerOne.util.AbbreviationResolver;
import ncbi.util.Profiler;

public class AbbreviationResolverProcessor extends TextInstanceProcessor {

	private static final long serialVersionUID = 1L;

	private AbbreviationResolver abbreviationResolver;

	public AbbreviationResolverProcessor(AbbreviationResolver abbreviationResolver) {
		this.abbreviationResolver = abbreviationResolver;
	}

	public AbbreviationResolver getAbbreviationResolver() {
		return abbreviationResolver;
	}

	@Override
	public void process(TextInstance input) {
		Profiler.start("AbbreviationResolverProcessor.process()");
		for (Segment segment : input.getSegments()) {
			// Do abbreviation pre-processing
			MentionName mentionName = segment.getMentionName();
			String id = input.getSourceId();
			abbreviationResolver.expand(id, mentionName);
		}
		Profiler.stop("AbbreviationResolverProcessor.process()");
	}

}
