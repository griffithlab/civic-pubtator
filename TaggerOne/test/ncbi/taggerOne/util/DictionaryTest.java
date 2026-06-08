package ncbi.taggerOne.util;

import static org.junit.Assert.*;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.ObjectInputStream;
import java.io.ObjectOutputStream;
import java.util.List;

import org.junit.Assert;
import org.junit.Test;

public class DictionaryTest {

	@Test
	public void test1() {
		Dictionary<String> dict = new Dictionary<String>();

		// Test no elements
		assertEquals(0, dict.size());
		assertFalse(dict.isFrozen());

		// Test a single element
		assertEquals(0, dict.addElement("e0"));
		assertEquals(1, dict.size());
		assertEquals(0, dict.getIndex("e0"));
		assertTrue(dict.getIndex("not present") < 0);
		assertEquals("e0", dict.getElement(0));
		assertFalse(dict.isFrozen());

		// Test multiple elements
		assertEquals(1, dict.addElement("e1"));
		assertEquals(2, dict.addElement("e2"));
		assertEquals(3, dict.addElement("e3"));
		assertEquals(4, dict.addElement("e4"));
		assertEquals(5, dict.size());
		assertTrue(dict.getIndex("not present") < 0);
		assertEquals(0, dict.getIndex("e0"));
		assertEquals("e0", dict.getElement(0));
		assertEquals(1, dict.getIndex("e1"));
		assertEquals("e1", dict.getElement(1));
		assertEquals(2, dict.getIndex("e2"));
		assertEquals("e2", dict.getElement(2));
		assertEquals(3, dict.getIndex("e3"));
		assertEquals("e3", dict.getElement(3));
		assertEquals(4, dict.getIndex("e4"));
		assertEquals("e4", dict.getElement(4));

		// Test re-adding the same elements
		assertEquals(0, dict.addElement("e0"));
		assertEquals(1, dict.addElement("e1"));
		assertEquals(2, dict.addElement("e2"));
		assertEquals(3, dict.addElement("e3"));
		assertEquals(4, dict.addElement("e4"));
		assertEquals(5, dict.size());
		assertEquals(0, dict.getIndex("e0"));
		assertEquals("e0", dict.getElement(0));
		assertEquals(1, dict.getIndex("e1"));
		assertEquals("e1", dict.getElement(1));
		assertEquals(2, dict.getIndex("e2"));
		assertEquals("e2", dict.getElement(2));
		assertEquals(3, dict.getIndex("e3"));
		assertEquals("e3", dict.getElement(3));
		assertEquals(4, dict.getIndex("e4"));
		assertEquals("e4", dict.getElement(4));

		assertFalse(dict.isFrozen());
		dict.freeze();
		assertTrue(dict.isFrozen());
		dict.freeze();
		assertTrue(dict.isFrozen());
	}

	@Test
	public void test2() {
		Dictionary<String> dict = new Dictionary<String>();

		// Test no elements
		List<String> elements = dict.getElements();
		assertEquals(0, elements.size());

		// Test a single element
		assertEquals(0, dict.addElement("e0"));
		elements = dict.getElements();
		assertEquals(1, elements.size());
		assertEquals("e0", elements.get(0));

		// Test multiple elements
		assertEquals(1, dict.addElement("e1"));
		assertEquals(2, dict.addElement("e2"));
		assertEquals(3, dict.addElement("e3"));
		assertEquals(4, dict.addElement("e4"));
		assertEquals("e0", dict.getElement(0));
		assertEquals("e1", dict.getElement(1));
		assertEquals("e2", dict.getElement(2));
		assertEquals("e3", dict.getElement(3));
		assertEquals("e4", dict.getElement(4));
		assertEquals(5, elements.size());
		assertEquals("e0", elements.get(0));
		assertEquals("e1", elements.get(1));
		assertEquals("e2", elements.get(2));
		assertEquals("e3", elements.get(3));
		assertEquals("e4", elements.get(4));
	}

	@Test
	public void test3() {
		Dictionary<String> dict = new Dictionary<String>();

		assertEquals(0, dict.size());
		assertFalse(dict.isFrozen());
		dict.freeze();
		assertTrue(dict.isFrozen());

		try {
			dict.addElement("e0");
			Assert.fail("Expected exception to be thrown");
		} catch (Exception e) {
			assertTrue(e instanceof IllegalStateException);
		}
	}

	@Test
	public void test4() {
		Dictionary<String> dict = new Dictionary<String>();

		int size = 10000;

		// Test adding many elements
		for (int i = 0; i < size; i++) {
			String str = "e" + i;
			dict.addElement(str);
			assertEquals(i + 1, dict.size());
		}
		dict.freeze();
		assertEquals(size, dict.size());

		for (int i = 0; i < size; i++) {
			String str = "e" + i;
			assertEquals(str, dict.getElement(i));
			assertEquals(i, dict.getIndex(str));
		}
	}

	@Test
	public void testEquals() {
		Dictionary<String> d = getDictionary(5);
		assertTrue(d.equals(d));
		assertFalse(d.equals(null));
		assertFalse(d.equals("string"));
		assertTrue(d.equals(getDictionary(5)));
		assertFalse(d.equals(getDictionary(1)));
	}

	@Test
	public void testHashCode() {
		Dictionary<String> d1a = getDictionary(147);
		Dictionary<String> d1b = getDictionary(147);
		Dictionary<String> d2a = getDictionary(93);
		Dictionary<String> d2b = getDictionary(93);

		assertTrue(d1a.hashCode() == d1b.hashCode());
		assertTrue(d2a.hashCode() == d2b.hashCode());
		assertFalse(d1a.hashCode() == d2a.hashCode());
		assertFalse(d1b.hashCode() == d2b.hashCode());

		d1b.freeze();
		d2b.freeze();

		assertTrue(d1a.hashCode() == d1b.hashCode());
		assertTrue(d2a.hashCode() == d2b.hashCode());
	}

	@Test
	@SuppressWarnings("unchecked")
	public void testSerialization() {
		Dictionary<String> dict = new Dictionary<String>();
		assertEquals(0, dict.addElement("e0"));
		assertEquals(1, dict.addElement("e1"));
		assertEquals(2, dict.addElement("e2"));
		assertEquals(3, dict.addElement("e3"));
		assertEquals(4, dict.addElement("e4"));
		dict.freeze();
		assertEquals("e0", dict.getElement(0));
		assertEquals("e1", dict.getElement(1));
		assertEquals("e2", dict.getElement(2));
		assertEquals("e3", dict.getElement(3));
		assertEquals("e4", dict.getElement(4));
		assertEquals(5, dict.size());
		assertTrue(dict.isFrozen());

		Dictionary<String> copy = null;
		try {
			ByteArrayOutputStream sink = new ByteArrayOutputStream();
			ObjectOutputStream oos = new ObjectOutputStream(sink);
			oos.writeObject(dict);
			byte[] data = sink.toByteArray();
			oos.close();
			ObjectInputStream ois = new ObjectInputStream(new ByteArrayInputStream(data));
			copy = (Dictionary<String>) ois.readObject();
			ois.close();
		} catch (Exception e) {
			Assert.fail("Caught exception: " + e);
		}

		assertEquals("e0", copy.getElement(0));
		assertEquals("e1", copy.getElement(1));
		assertEquals("e2", copy.getElement(2));
		assertEquals("e3", copy.getElement(3));
		assertEquals("e4", copy.getElement(4));
		assertEquals(5, copy.size());
		assertTrue(copy.isFrozen());
	}

	private static Dictionary<String> getDictionary(int size) {
		Dictionary<String> dict = new Dictionary<String>();
		for (int i = 0; i < size; i++) {
			dict.addElement("e" + i);
		}
		return dict;
	}
}
