package ncbi.taggerOne.types;

import static org.junit.Assert.*;

import org.junit.Assert;
import org.junit.Test;

public class TextInstanceTest {

	@Test
	public void testCreate() {
		String text = "A common human skin tumour is caused by activating mutations in beta-catenin.";
		TextInstance instance = new TextInstance("123456-00", "123456", text, 23);
		assertEquals("123456-00", instance.getInstanceId());
		assertEquals("123456", instance.getSourceId());
		assertEquals(text, instance.getText());
		assertEquals(23, instance.getOffset());
		assertNull("Tokens should be null", instance.getTokens());
		assertNull("Segments should be null", instance.getSegments());
		assertNull("TargetAnnotation should be null", instance.getTargetAnnotation());
		assertNull("TargetStateSequence should be null", instance.getTargetStateSequence());
		assertNull("PredictedStates should be null", instance.getPredictedStates());
		assertNull("PredictedAnnotations should be null", instance.getPredictedAnnotations());
	}

	@Test
	public void testExceptions() {
		String text = "A common human skin tumour is caused by activating mutations in beta-catenin.";
		@SuppressWarnings("unused")
		TextInstance i = null;
		try {
			i = new TextInstance(null, "123456", text, 23);
			Assert.fail("Expected exception to be thrown");
		} catch (Exception e) {
			assertTrue(e instanceof IllegalArgumentException);
		}
		try {
			i = new TextInstance("123456-00", null, text, 23);
			Assert.fail("Expected exception to be thrown");
		} catch (Exception e) {
			assertTrue(e instanceof IllegalArgumentException);
		}
		try {
			i = new TextInstance("123456-00", "123456", null, 23);
			Assert.fail("Expected exception to be thrown");
		} catch (Exception e) {
			assertTrue(e instanceof IllegalArgumentException);
		}
		try {
			i = new TextInstance("123456-00", "123456", text, -1);
			Assert.fail("Expected exception to be thrown");
		} catch (Exception e) {
			assertTrue(e instanceof IllegalArgumentException);
		}
	}

	@Test
	public void testEqualsAndHashCode() {
		String text = "A common human skin tumour is caused by activating mutations in beta-catenin.";
		TextInstance i = new TextInstance("123456-00", "123456", text, 23);
		assertTrue(i.equals(i));
		assertFalse(i.equals(null));
		assertFalse(i.equals("string"));
		TextInstance i2 = new TextInstance("123456-00", "123456", text, 23);
		assertTrue(i.equals(i2));
		assertTrue(i.hashCode() == i2.hashCode());
		TextInstance i3 = new TextInstance("123456-01", "123456", "HFE mutations analysis in 711 hemochromatosis probands", 42);
		assertFalse(i.equals(i3));
		assertFalse(i.hashCode() == i3.hashCode());
	}

}
