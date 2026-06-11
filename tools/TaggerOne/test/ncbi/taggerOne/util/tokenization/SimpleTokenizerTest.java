package ncbi.taggerOne.util.tokenization;

import static org.junit.Assert.*;

import org.junit.Test;

public class SimpleTokenizerTest {

	@Test
	public void test1() {
		SimpleTokenizer t = new SimpleTokenizer();
		t.reset("test");
		assertTrue(t.nextToken());
		assertEquals(0, t.startChar());
		assertEquals(4, t.endChar());
		assertFalse(t.nextToken());
	}

	@Test
	public void test2() {
		SimpleTokenizer t = new SimpleTokenizer();
		t.reset("");
		assertFalse(t.nextToken());
	}

	@Test
	public void test3() {
		SimpleTokenizer t = new SimpleTokenizer();
		String str = "Germline BRCA1 alterations +- S65C hERB";
		t.reset(str);
		assertTrue(t.nextToken());
		assertEquals("Germline", str.substring(t.startChar(), t.endChar()));
		assertEquals(0, t.startChar());
		assertEquals(8, t.endChar());
		assertTrue(t.nextToken());
		assertEquals("BRCA1", str.substring(t.startChar(), t.endChar()));
		assertEquals(9, t.startChar());
		assertEquals(14, t.endChar());
		assertTrue(t.nextToken());
		assertEquals("alterations", str.substring(t.startChar(), t.endChar()));
		assertEquals(15, t.startChar());
		assertEquals(26, t.endChar());
		assertTrue(t.nextToken());
		assertEquals("+", str.substring(t.startChar(), t.endChar()));
		assertEquals(27, t.startChar());
		assertEquals(28, t.endChar());
		assertTrue(t.nextToken());
		assertEquals("-", str.substring(t.startChar(), t.endChar()));
		assertEquals(28, t.startChar());
		assertEquals(29, t.endChar());
		assertTrue(t.nextToken());
		assertEquals("S65C", str.substring(t.startChar(), t.endChar()));
		assertEquals(30, t.startChar());
		assertEquals(34, t.endChar());
		assertTrue(t.nextToken());
		assertEquals("hERB", str.substring(t.startChar(), t.endChar()));
		assertEquals(35, t.startChar());
		assertEquals(39, t.endChar());
		assertFalse(t.nextToken());
	}

	@Test
	public void test4() {
		SimpleTokenizer t = new SimpleTokenizer();
		t.reset("test ");
		assertTrue(t.nextToken());
		assertEquals(0, t.startChar());
		assertEquals(4, t.endChar());
		assertFalse(t.nextToken());
	}

	@Test
	public void test5() {
		SimpleTokenizer t = new SimpleTokenizer();
		String text = "3′,4′-bis-difluoromethoxycinnamoylanthranilate";
		t.reset(text);
		assertTrue(t.nextToken());
		assertEquals("3", text.substring(t.startChar(), t.endChar()));
		assertTrue(t.nextToken());
		assertEquals("′", text.substring(t.startChar(), t.endChar()));
		assertTrue(t.nextToken());
		assertEquals(",", text.substring(t.startChar(), t.endChar()));
		assertTrue(t.nextToken());
		assertEquals("4", text.substring(t.startChar(), t.endChar()));
		assertTrue(t.nextToken());
		assertEquals("′", text.substring(t.startChar(), t.endChar()));
		assertTrue(t.nextToken());
		assertEquals("-", text.substring(t.startChar(), t.endChar()));
		assertTrue(t.nextToken());
		assertEquals("bis", text.substring(t.startChar(), t.endChar()));
		assertTrue(t.nextToken());
		assertEquals("-", text.substring(t.startChar(), t.endChar()));
		assertTrue(t.nextToken());
		assertEquals("difluoromethoxycinnamoylanthranilate", text.substring(t.startChar(), t.endChar()));
		assertFalse(t.nextToken());
	}

	@Test
	public void test6() {
		SimpleTokenizer t = new SimpleTokenizer();
		String text = "N¬-(4-phenylthiazol)acetamide";
		t.reset(text);
		assertTrue(t.nextToken());
		assertEquals("N", text.substring(t.startChar(), t.endChar()));
		assertTrue(t.nextToken());
		assertEquals("¬", text.substring(t.startChar(), t.endChar()));
		assertTrue(t.nextToken());
		assertEquals("-", text.substring(t.startChar(), t.endChar()));
		assertTrue(t.nextToken());
		assertEquals("(", text.substring(t.startChar(), t.endChar()));
		assertTrue(t.nextToken());
		assertEquals("4", text.substring(t.startChar(), t.endChar()));
		assertTrue(t.nextToken());
		assertEquals("-", text.substring(t.startChar(), t.endChar()));
		assertTrue(t.nextToken());
		assertEquals("phenylthiazol", text.substring(t.startChar(), t.endChar()));
		assertTrue(t.nextToken());
		assertEquals(")", text.substring(t.startChar(), t.endChar()));
		assertTrue(t.nextToken());
		assertEquals("acetamide", text.substring(t.startChar(), t.endChar()));
	}
}
