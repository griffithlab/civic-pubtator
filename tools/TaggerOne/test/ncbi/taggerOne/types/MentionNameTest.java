package ncbi.taggerOne.types;

import static org.junit.Assert.*;

import java.util.ArrayList;
import java.util.List;

import org.junit.Assert;
import org.junit.Test;

public class MentionNameTest {

	@Test
	public void testCreate() {
		MentionName name = new MentionName("reversible inferior defect");
		assertEquals("reversible inferior defect", name.getName());
		assertFalse(name.isLabel());
		assertNull(name.getTokens());
		assertNull(name.getVector());
		assertTrue(name.equals(name));
		assertFalse(name.equals(null));
		assertFalse(name.equals("string"));
		MentionName name2 = new MentionName("reversible inferior defect");
		assertTrue(name.equals(name2));
		assertTrue(name.hashCode() == name2.hashCode());
		MentionName name3 = new MentionName("chronic inflammation");
		assertFalse(name.equals(name3));
		assertFalse(name.hashCode() == name3.hashCode());
		name.setName("reversible anterior defect");
		assertEquals("reversible anterior defect", name.getName());
		assertTrue(name.equals(new MentionName("reversible anterior defect")));
	}

	@Test
	public void testCreateLabel() {
		MentionName name = new MentionName(true, "LABEL1");
		assertEquals("LABEL1", name.getName());
		assertTrue(name.isLabel());
		List<String> tokens = name.getTokens();
		assertEquals(1, tokens.size());
		assertEquals("LABEL1", tokens.get(0));
		assertNull(name.getVector());
		assertFalse(name.equals(null));
		assertFalse(name.equals("string"));
		MentionName name2 = new MentionName(true, "LABEL1");
		assertTrue(name.equals(name2));
		assertTrue(name.hashCode() == name2.hashCode());
		MentionName name3 = new MentionName(true, "LABEL2");
		assertFalse(name.equals(name3));
		assertFalse(name.hashCode() == name3.hashCode());
		MentionName name4 = new MentionName(false, "LABEL1");
		assertFalse(name.equals(name4));
		assertFalse(name.hashCode() == name4.hashCode());
	}

	@Test
	public void testExceptions() {
		MentionName name = null;
		try {
			name = new MentionName(true, null);
			Assert.fail("Expected exception to be thrown");
		} catch (Exception e) {
			assertTrue(e instanceof IllegalArgumentException);
		}
		try {
			name = new MentionName(false, null);
			Assert.fail("Expected exception to be thrown");
		} catch (Exception e) {
			assertTrue(e instanceof IllegalArgumentException);
		}
		name = new MentionName(true, "LABEL1");
		try {
			name.setName("LABEL2");
			Assert.fail("Expected exception to be thrown");
		} catch (Exception e) {
			assertTrue(e instanceof IllegalArgumentException);
		}
		List<String> tokens = new ArrayList<String>();
		tokens.add("LABEL1");
		try {
			name.setTokens(tokens);
			Assert.fail("Expected exception to be thrown");
		} catch (Exception e) {
			assertTrue(e instanceof IllegalArgumentException);
		}
	}

}
