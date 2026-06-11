package ncbi.taggerOne.util.tokenization;

import static org.junit.Assert.*;

import org.junit.Test;

public class FinerTokenizerTest {

	@Test
	public void test1() {
		FinerTokenizer t = new FinerTokenizer();
		t.reset("test");
		assertTrue(t.nextToken());
		assertEquals(0, t.startChar());
		assertEquals(4, t.endChar());
		assertFalse(t.nextToken());
	}

	@Test
	public void test2() {
		FinerTokenizer t = new FinerTokenizer();
		t.reset("");
		assertFalse(t.nextToken());
	}

	@Test
	public void test3() {
		FinerTokenizer t = new FinerTokenizer();
		String str = "Germline BRCA1 alterations -- S65C hERB";
		t.reset(str);
		assertTrue(t.nextToken());
		assertEquals("Germline", str.substring(t.startChar(), t.endChar()));
		assertEquals(0, t.startChar());
		assertEquals(8, t.endChar());
		assertTrue(t.nextToken());
		assertEquals("BRCA", str.substring(t.startChar(), t.endChar()));
		assertEquals(9, t.startChar());
		assertEquals(13, t.endChar());
		assertTrue(t.nextToken());
		assertEquals("1", str.substring(t.startChar(), t.endChar()));
		assertEquals(13, t.startChar());
		assertEquals(14, t.endChar());
		assertTrue(t.nextToken());
		assertEquals("alterations", str.substring(t.startChar(), t.endChar()));
		assertEquals(15, t.startChar());
		assertEquals(26, t.endChar());
		assertTrue(t.nextToken());
		assertEquals("-", str.substring(t.startChar(), t.endChar()));
		assertEquals(27, t.startChar());
		assertEquals(28, t.endChar());
		assertTrue(t.nextToken());
		assertEquals("-", str.substring(t.startChar(), t.endChar()));
		assertEquals(28, t.startChar());
		assertEquals(29, t.endChar());
		assertTrue(t.nextToken());
		assertEquals("S", str.substring(t.startChar(), t.endChar()));
		assertEquals(30, t.startChar());
		assertEquals(31, t.endChar());
		assertTrue(t.nextToken());
		assertEquals("65", str.substring(t.startChar(), t.endChar()));
		assertEquals(31, t.startChar());
		assertEquals(33, t.endChar());
		assertTrue(t.nextToken());
		assertEquals("C", str.substring(t.startChar(), t.endChar()));
		assertEquals(33, t.startChar());
		assertEquals(34, t.endChar());
		assertTrue(t.nextToken());
		assertEquals("h", str.substring(t.startChar(), t.endChar()));
		assertEquals(35, t.startChar());
		assertEquals(36, t.endChar());
		assertTrue(t.nextToken());
		assertEquals("ERB", str.substring(t.startChar(), t.endChar()));
		assertEquals(36, t.startChar());
		assertEquals(39, t.endChar());
		assertFalse(t.nextToken());
	}

	@Test
	public void test4() {
		FinerTokenizer t = new FinerTokenizer();
		t.reset("test ");
		assertTrue(t.nextToken());
		assertEquals(0, t.startChar());
		assertEquals(4, t.endChar());
		assertFalse(t.nextToken());
	}

	@Test
	public void test5() {
		FinerTokenizer t = new FinerTokenizer();
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
		FinerTokenizer t = new FinerTokenizer();
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
