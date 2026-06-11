package ncbi.taggerOne.util;

import static org.junit.Assert.*;

import org.junit.Assert;
import org.junit.Test;

public class RankedListTest {

	@Test
	public void test1() {
		RankedList<String> list = new RankedList<String>(1);

		assertEquals(1, list.maxSize());
		assertEquals(0, list.size());
		assertTrue(list.check(0.0));
		assertTrue(list.check(0.5));
		assertTrue(list.check(1.0));

		assertEquals(-1, list.find("e0"));
		assertEquals(-1, list.find("e1"));
		assertEquals(-1, list.find("e2"));
		assertEquals(-1, list.find("e3"));
		assertEquals(-1, list.find("e4"));
		assertEquals(-1, list.find("e5"));
		assertEquals(-1, list.find("e6"));
		assertEquals(-1, list.find("e7"));
		assertEquals(-1, list.find("e8"));
		assertEquals(-1, list.find("e9"));

		list.add(0.43, "e0");

		assertEquals(1, list.maxSize());
		assertEquals(1, list.size());
		assertFalse(list.check(0.0));
		assertTrue(list.check(0.5));
		assertTrue(list.check(1.0));

		assertEquals("e0", list.getObject(0));
		assertEquals(0.43, list.getValue(0), 0.0);

		assertEquals(0, list.find("e0"));
		assertEquals(-1, list.find("e1"));
		assertEquals(-1, list.find("e2"));
		assertEquals(-1, list.find("e3"));
		assertEquals(-1, list.find("e4"));
		assertEquals(-1, list.find("e5"));
		assertEquals(-1, list.find("e6"));
		assertEquals(-1, list.find("e7"));
		assertEquals(-1, list.find("e8"));
		assertEquals(-1, list.find("e9"));

		list.add(0.57, "e1");

		assertEquals(1, list.maxSize());
		assertEquals(1, list.size());
		assertFalse(list.check(0.0));
		assertFalse(list.check(0.5));
		assertTrue(list.check(1.0));

		assertEquals("e1", list.getObject(0));
		assertEquals(0.57, list.getValue(0), 0.0);

		assertEquals(-1, list.find("e0"));
		assertEquals(0, list.find("e1"));
		assertEquals(-1, list.find("e2"));
		assertEquals(-1, list.find("e3"));
		assertEquals(-1, list.find("e4"));
		assertEquals(-1, list.find("e5"));
		assertEquals(-1, list.find("e6"));
		assertEquals(-1, list.find("e7"));
		assertEquals(-1, list.find("e8"));
		assertEquals(-1, list.find("e9"));

		list.add(0.13, "e2");

		assertEquals(1, list.maxSize());
		assertEquals(1, list.size());
		assertFalse(list.check(0.0));
		assertFalse(list.check(0.5));
		assertTrue(list.check(1.0));

		assertEquals("e1", list.getObject(0));
		assertEquals(0.57, list.getValue(0), 0.0);

		assertEquals(-1, list.find("e0"));
		assertEquals(0, list.find("e1"));
		assertEquals(-1, list.find("e2"));
		assertEquals(-1, list.find("e3"));
		assertEquals(-1, list.find("e4"));
		assertEquals(-1, list.find("e5"));
		assertEquals(-1, list.find("e6"));
		assertEquals(-1, list.find("e7"));
		assertEquals(-1, list.find("e8"));
		assertEquals(-1, list.find("e9"));

		list.add(0.52, "e3");

		assertEquals(1, list.maxSize());
		assertEquals(1, list.size());
		assertFalse(list.check(0.0));
		assertFalse(list.check(0.5));
		assertTrue(list.check(1.0));

		assertEquals("e1", list.getObject(0));
		assertEquals(0.57, list.getValue(0), 0.0);

		assertEquals(-1, list.find("e0"));
		assertEquals(0, list.find("e1"));
		assertEquals(-1, list.find("e2"));
		assertEquals(-1, list.find("e3"));
		assertEquals(-1, list.find("e4"));
		assertEquals(-1, list.find("e5"));
		assertEquals(-1, list.find("e6"));
		assertEquals(-1, list.find("e7"));
		assertEquals(-1, list.find("e8"));
		assertEquals(-1, list.find("e9"));

		list.add(0.69, "e4");

		assertEquals(1, list.maxSize());
		assertEquals(1, list.size());
		assertFalse(list.check(0.0));
		assertFalse(list.check(0.5));
		assertTrue(list.check(1.0));

		assertEquals("e4", list.getObject(0));
		assertEquals(0.69, list.getValue(0), 0.0);

		assertEquals(-1, list.find("e0"));
		assertEquals(-1, list.find("e1"));
		assertEquals(-1, list.find("e2"));
		assertEquals(-1, list.find("e3"));
		assertEquals(0, list.find("e4"));
		assertEquals(-1, list.find("e5"));
		assertEquals(-1, list.find("e6"));
		assertEquals(-1, list.find("e7"));
		assertEquals(-1, list.find("e8"));
		assertEquals(-1, list.find("e9"));

		list.add(0.61, "e5");

		assertEquals(1, list.maxSize());
		assertEquals(1, list.size());
		assertFalse(list.check(0.0));
		assertFalse(list.check(0.5));
		assertTrue(list.check(1.0));

		assertEquals("e4", list.getObject(0));
		assertEquals(0.69, list.getValue(0), 0.0);

		assertEquals(-1, list.find("e0"));
		assertEquals(-1, list.find("e1"));
		assertEquals(-1, list.find("e2"));
		assertEquals(-1, list.find("e3"));
		assertEquals(0, list.find("e4"));
		assertEquals(-1, list.find("e5"));
		assertEquals(-1, list.find("e6"));
		assertEquals(-1, list.find("e7"));
		assertEquals(-1, list.find("e8"));
		assertEquals(-1, list.find("e9"));

		list.add(0.07, "e6");

		assertEquals(1, list.maxSize());
		assertEquals(1, list.size());
		assertFalse(list.check(0.0));
		assertFalse(list.check(0.5));
		assertTrue(list.check(1.0));

		assertEquals("e4", list.getObject(0));
		assertEquals(0.69, list.getValue(0), 0.0);

		assertEquals(-1, list.find("e0"));
		assertEquals(-1, list.find("e1"));
		assertEquals(-1, list.find("e2"));
		assertEquals(-1, list.find("e3"));
		assertEquals(0, list.find("e4"));
		assertEquals(-1, list.find("e5"));
		assertEquals(-1, list.find("e6"));
		assertEquals(-1, list.find("e7"));
		assertEquals(-1, list.find("e8"));
		assertEquals(-1, list.find("e9"));

		list.add(0.20, "e7");

		assertEquals(1, list.maxSize());
		assertEquals(1, list.size());
		assertFalse(list.check(0.0));
		assertFalse(list.check(0.5));
		assertTrue(list.check(1.0));

		assertEquals("e4", list.getObject(0));
		assertEquals(0.69, list.getValue(0), 0.0);

		assertEquals(-1, list.find("e0"));
		assertEquals(-1, list.find("e1"));
		assertEquals(-1, list.find("e2"));
		assertEquals(-1, list.find("e3"));
		assertEquals(0, list.find("e4"));
		assertEquals(-1, list.find("e5"));
		assertEquals(-1, list.find("e6"));
		assertEquals(-1, list.find("e7"));
		assertEquals(-1, list.find("e8"));
		assertEquals(-1, list.find("e9"));

		list.add(0.28, "e8");

		assertEquals(1, list.maxSize());
		assertEquals(1, list.size());
		assertFalse(list.check(0.0));
		assertFalse(list.check(0.5));
		assertTrue(list.check(1.0));

		assertEquals("e4", list.getObject(0));
		assertEquals(0.69, list.getValue(0), 0.0);

		assertEquals(-1, list.find("e0"));
		assertEquals(-1, list.find("e1"));
		assertEquals(-1, list.find("e2"));
		assertEquals(-1, list.find("e3"));
		assertEquals(0, list.find("e4"));
		assertEquals(-1, list.find("e5"));
		assertEquals(-1, list.find("e6"));
		assertEquals(-1, list.find("e7"));
		assertEquals(-1, list.find("e8"));
		assertEquals(-1, list.find("e9"));

		list.add(0.76, "e9");

		assertEquals(1, list.maxSize());
		assertEquals(1, list.size());
		assertFalse(list.check(0.0));
		assertFalse(list.check(0.5));
		assertTrue(list.check(1.0));

		assertEquals("e9", list.getObject(0));
		assertEquals(0.76, list.getValue(0), 0.0);

		assertEquals(-1, list.find("e0"));
		assertEquals(-1, list.find("e1"));
		assertEquals(-1, list.find("e2"));
		assertEquals(-1, list.find("e3"));
		assertEquals(-1, list.find("e4"));
		assertEquals(-1, list.find("e5"));
		assertEquals(-1, list.find("e6"));
		assertEquals(-1, list.find("e7"));
		assertEquals(-1, list.find("e8"));
		assertEquals(0, list.find("e9"));

		list.clear();

		assertEquals(1, list.maxSize());
		assertEquals(0, list.size());
		assertTrue(list.check(0.0));
		assertTrue(list.check(0.5));
		assertTrue(list.check(1.0));
	}

	@Test
	public void test5() {
		RankedList<String> list = new RankedList<String>(5);

		assertEquals(5, list.maxSize());
		assertEquals(0, list.size());
		assertTrue(list.check(0.0));
		assertTrue(list.check(0.5));
		assertTrue(list.check(1.0));

		assertEquals(-1, list.find("e0"));
		assertEquals(-1, list.find("e1"));
		assertEquals(-1, list.find("e2"));
		assertEquals(-1, list.find("e3"));
		assertEquals(-1, list.find("e4"));
		assertEquals(-1, list.find("e5"));
		assertEquals(-1, list.find("e6"));
		assertEquals(-1, list.find("e7"));
		assertEquals(-1, list.find("e8"));
		assertEquals(-1, list.find("e9"));

		list.add(0.96, "e0");

		assertEquals(5, list.maxSize());
		assertEquals(1, list.size());
		assertTrue(list.check(0.0));
		assertTrue(list.check(0.5));
		assertTrue(list.check(1.0));

		assertEquals("e0", list.getObject(0));
		assertEquals(0.96, list.getValue(0), 0.0);

		assertEquals(0, list.find("e0"));
		assertEquals(-1, list.find("e1"));
		assertEquals(-1, list.find("e2"));
		assertEquals(-1, list.find("e3"));
		assertEquals(-1, list.find("e4"));
		assertEquals(-1, list.find("e5"));
		assertEquals(-1, list.find("e6"));
		assertEquals(-1, list.find("e7"));
		assertEquals(-1, list.find("e8"));
		assertEquals(-1, list.find("e9"));

		list.add(0.01, "e1");

		assertEquals(5, list.maxSize());
		assertEquals(2, list.size());
		assertTrue(list.check(0.0));
		assertTrue(list.check(0.5));
		assertTrue(list.check(1.0));

		assertEquals("e0", list.getObject(0));
		assertEquals(0.96, list.getValue(0), 0.0);
		assertEquals("e1", list.getObject(1));
		assertEquals(0.01, list.getValue(1), 0.0);

		assertEquals(0, list.find("e0"));
		assertEquals(1, list.find("e1"));
		assertEquals(-1, list.find("e2"));
		assertEquals(-1, list.find("e3"));
		assertEquals(-1, list.find("e4"));
		assertEquals(-1, list.find("e5"));
		assertEquals(-1, list.find("e6"));
		assertEquals(-1, list.find("e7"));
		assertEquals(-1, list.find("e8"));
		assertEquals(-1, list.find("e9"));

		list.add(0.44, "e2");

		assertEquals(5, list.maxSize());
		assertEquals(3, list.size());
		assertTrue(list.check(0.0));
		assertTrue(list.check(0.5));
		assertTrue(list.check(1.0));

		assertEquals("e0", list.getObject(0));
		assertEquals(0.96, list.getValue(0), 0.0);
		assertEquals("e2", list.getObject(1));
		assertEquals(0.44, list.getValue(1), 0.0);
		assertEquals("e1", list.getObject(2));
		assertEquals(0.01, list.getValue(2), 0.0);

		assertEquals(0, list.find("e0"));
		assertEquals(2, list.find("e1"));
		assertEquals(1, list.find("e2"));
		assertEquals(-1, list.find("e3"));
		assertEquals(-1, list.find("e4"));
		assertEquals(-1, list.find("e5"));
		assertEquals(-1, list.find("e6"));
		assertEquals(-1, list.find("e7"));
		assertEquals(-1, list.find("e8"));
		assertEquals(-1, list.find("e9"));

		list.add(0.57, "e3");

		assertEquals(5, list.maxSize());
		assertEquals(4, list.size());
		assertTrue(list.check(0.0));
		assertTrue(list.check(0.5));
		assertTrue(list.check(1.0));

		assertEquals("e0", list.getObject(0));
		assertEquals(0.96, list.getValue(0), 0.0);
		assertEquals("e3", list.getObject(1));
		assertEquals(0.57, list.getValue(1), 0.0);
		assertEquals("e2", list.getObject(2));
		assertEquals(0.44, list.getValue(2), 0.0);
		assertEquals("e1", list.getObject(3));
		assertEquals(0.01, list.getValue(3), 0.0);

		assertEquals(0, list.find("e0"));
		assertEquals(3, list.find("e1"));
		assertEquals(2, list.find("e2"));
		assertEquals(1, list.find("e3"));
		assertEquals(-1, list.find("e4"));
		assertEquals(-1, list.find("e5"));
		assertEquals(-1, list.find("e6"));
		assertEquals(-1, list.find("e7"));
		assertEquals(-1, list.find("e8"));
		assertEquals(-1, list.find("e9"));

		list.add(0.31, "e4");

		assertEquals(5, list.maxSize());
		assertEquals(5, list.size());
		assertFalse(list.check(0.0));
		assertTrue(list.check(0.5));
		assertTrue(list.check(1.0));

		assertEquals("e0", list.getObject(0));
		assertEquals(0.96, list.getValue(0), 0.0);
		assertEquals("e3", list.getObject(1));
		assertEquals(0.57, list.getValue(1), 0.0);
		assertEquals("e2", list.getObject(2));
		assertEquals(0.44, list.getValue(2), 0.0);
		assertEquals("e4", list.getObject(3));
		assertEquals(0.31, list.getValue(3), 0.0);
		assertEquals("e1", list.getObject(4));
		assertEquals(0.01, list.getValue(4), 0.0);

		assertEquals(0, list.find("e0"));
		assertEquals(4, list.find("e1"));
		assertEquals(2, list.find("e2"));
		assertEquals(1, list.find("e3"));
		assertEquals(3, list.find("e4"));
		assertEquals(-1, list.find("e5"));
		assertEquals(-1, list.find("e6"));
		assertEquals(-1, list.find("e7"));
		assertEquals(-1, list.find("e8"));
		assertEquals(-1, list.find("e9"));

		list.add(0.98, "e5");

		assertEquals(5, list.maxSize());
		assertEquals(5, list.size());
		assertFalse(list.check(0.0));
		assertTrue(list.check(0.5));
		assertTrue(list.check(1.0));

		assertEquals("e5", list.getObject(0));
		assertEquals(0.98, list.getValue(0), 0.0);
		assertEquals("e0", list.getObject(1));
		assertEquals(0.96, list.getValue(1), 0.0);
		assertEquals("e3", list.getObject(2));
		assertEquals(0.57, list.getValue(2), 0.0);
		assertEquals("e2", list.getObject(3));
		assertEquals(0.44, list.getValue(3), 0.0);
		assertEquals("e4", list.getObject(4));
		assertEquals(0.31, list.getValue(4), 0.0);

		assertEquals(1, list.find("e0"));
		assertEquals(-1, list.find("e1"));
		assertEquals(3, list.find("e2"));
		assertEquals(2, list.find("e3"));
		assertEquals(4, list.find("e4"));
		assertEquals(0, list.find("e5"));
		assertEquals(-1, list.find("e6"));
		assertEquals(-1, list.find("e7"));
		assertEquals(-1, list.find("e8"));
		assertEquals(-1, list.find("e9"));

		list.add(0.80, "e6");

		assertEquals(5, list.maxSize());
		assertEquals(5, list.size());
		assertFalse(list.check(0.0));
		assertTrue(list.check(0.5));
		assertTrue(list.check(1.0));

		assertEquals("e5", list.getObject(0));
		assertEquals(0.98, list.getValue(0), 0.0);
		assertEquals("e0", list.getObject(1));
		assertEquals(0.96, list.getValue(1), 0.0);
		assertEquals("e6", list.getObject(2));
		assertEquals(0.80, list.getValue(2), 0.0);
		assertEquals("e3", list.getObject(3));
		assertEquals(0.57, list.getValue(3), 0.0);
		assertEquals("e2", list.getObject(4));
		assertEquals(0.44, list.getValue(4), 0.0);

		assertEquals(1, list.find("e0"));
		assertEquals(-1, list.find("e1"));
		assertEquals(4, list.find("e2"));
		assertEquals(3, list.find("e3"));
		assertEquals(-1, list.find("e4"));
		assertEquals(0, list.find("e5"));
		assertEquals(2, list.find("e6"));
		assertEquals(-1, list.find("e7"));
		assertEquals(-1, list.find("e8"));
		assertEquals(-1, list.find("e9"));

		list.add(0.34, "e7");

		assertEquals(5, list.maxSize());
		assertEquals(5, list.size());
		assertFalse(list.check(0.0));
		assertTrue(list.check(0.5));
		assertTrue(list.check(1.0));

		assertEquals("e5", list.getObject(0));
		assertEquals(0.98, list.getValue(0), 0.0);
		assertEquals("e0", list.getObject(1));
		assertEquals(0.96, list.getValue(1), 0.0);
		assertEquals("e6", list.getObject(2));
		assertEquals(0.80, list.getValue(2), 0.0);
		assertEquals("e3", list.getObject(3));
		assertEquals(0.57, list.getValue(3), 0.0);
		assertEquals("e2", list.getObject(4));
		assertEquals(0.44, list.getValue(4), 0.0);

		assertEquals(1, list.find("e0"));
		assertEquals(-1, list.find("e1"));
		assertEquals(4, list.find("e2"));
		assertEquals(3, list.find("e3"));
		assertEquals(-1, list.find("e4"));
		assertEquals(0, list.find("e5"));
		assertEquals(2, list.find("e6"));
		assertEquals(-1, list.find("e7"));
		assertEquals(-1, list.find("e8"));
		assertEquals(-1, list.find("e9"));

		list.add(0.23, "e8");

		assertEquals(5, list.maxSize());
		assertEquals(5, list.size());
		assertFalse(list.check(0.0));
		assertTrue(list.check(0.5));
		assertTrue(list.check(1.0));

		assertEquals("e5", list.getObject(0));
		assertEquals(0.98, list.getValue(0), 0.0);
		assertEquals("e0", list.getObject(1));
		assertEquals(0.96, list.getValue(1), 0.0);
		assertEquals("e6", list.getObject(2));
		assertEquals(0.80, list.getValue(2), 0.0);
		assertEquals("e3", list.getObject(3));
		assertEquals(0.57, list.getValue(3), 0.0);
		assertEquals("e2", list.getObject(4));
		assertEquals(0.44, list.getValue(4), 0.0);

		assertEquals(1, list.find("e0"));
		assertEquals(-1, list.find("e1"));
		assertEquals(4, list.find("e2"));
		assertEquals(3, list.find("e3"));
		assertEquals(-1, list.find("e4"));
		assertEquals(0, list.find("e5"));
		assertEquals(2, list.find("e6"));
		assertEquals(-1, list.find("e7"));
		assertEquals(-1, list.find("e8"));
		assertEquals(-1, list.find("e9"));

		list.add(0.52, "e9");

		assertEquals(5, list.maxSize());
		assertEquals(5, list.size());
		assertFalse(list.check(0.0));
		assertFalse(list.check(0.5));
		assertTrue(list.check(1.0));

		assertEquals("e5", list.getObject(0));
		assertEquals(0.98, list.getValue(0), 0.0);
		assertEquals("e0", list.getObject(1));
		assertEquals(0.96, list.getValue(1), 0.0);
		assertEquals("e6", list.getObject(2));
		assertEquals(0.80, list.getValue(2), 0.0);
		assertEquals("e3", list.getObject(3));
		assertEquals(0.57, list.getValue(3), 0.0);
		assertEquals("e9", list.getObject(4));
		assertEquals(0.52, list.getValue(4), 0.0);

		assertEquals(1, list.find("e0"));
		assertEquals(-1, list.find("e1"));
		assertEquals(-1, list.find("e2"));
		assertEquals(3, list.find("e3"));
		assertEquals(-1, list.find("e4"));
		assertEquals(0, list.find("e5"));
		assertEquals(2, list.find("e6"));
		assertEquals(-1, list.find("e7"));
		assertEquals(-1, list.find("e8"));
		assertEquals(4, list.find("e9"));

		list.clear();

		assertEquals(5, list.maxSize());
		assertEquals(0, list.size());
		assertTrue(list.check(0.0));
		assertTrue(list.check(0.5));
		assertTrue(list.check(1.0));
	}

	@Test
	public void testOrdering() {
		RankedList<String> list = new RankedList<String>(5);
		list.add(0.5, "e0");
		list.add(0.5, "e1");
		list.add(0.5, "e2");
		list.add(0.5, "e3");
		list.add(0.5, "e4");
		assertEquals(5, list.size());
		assertEquals("e0", list.getObject(0));
		assertEquals(0.5, list.getValue(0), 0.0);
		assertEquals("e1", list.getObject(1));
		assertEquals(0.5, list.getValue(1), 0.0);
		assertEquals("e2", list.getObject(2));
		assertEquals(0.5, list.getValue(2), 0.0);
		assertEquals("e3", list.getObject(3));
		assertEquals(0.5, list.getValue(3), 0.0);
		assertEquals("e4", list.getObject(4));
		assertEquals(0.5, list.getValue(4), 0.0);
	}
	
	@Test
	public void testExceptions() {
		RankedList<String> list = null;
		try {
			list = new RankedList<String>(-1);
			Assert.fail("Expected exception to be thrown");
		} catch (Exception e) {
			assertTrue(e instanceof NegativeArraySizeException);
		}
		list = new RankedList<String>(2);
		assertEquals(0, list.size());
		try {
			list.getObject(0);
			Assert.fail("Expected exception to be thrown");
		} catch (Exception e) {
			assertTrue(e instanceof IndexOutOfBoundsException);
		}
		try {
			list.getValue(0);
			Assert.fail("Expected exception to be thrown");
		} catch (Exception e) {
			assertTrue(e instanceof IndexOutOfBoundsException);
		}
		list.add(0.5, "e0");
		assertEquals(1, list.size());
		try {
			list.getObject(1);
			Assert.fail("Expected exception to be thrown");
		} catch (Exception e) {
			assertTrue(e instanceof IndexOutOfBoundsException);
		}
		try {
			list.getValue(1);
			Assert.fail("Expected exception to be thrown");
		} catch (Exception e) {
			assertTrue(e instanceof IndexOutOfBoundsException);
		}
		list.add(0.7, "e1");
		assertEquals(2, list.size());
		try {
			list.getObject(2);
			Assert.fail("Expected exception to be thrown");
		} catch (Exception e) {
			assertTrue(e instanceof IndexOutOfBoundsException);
		}
		try {
			list.getValue(2);
			Assert.fail("Expected exception to be thrown");
		} catch (Exception e) {
			assertTrue(e instanceof IndexOutOfBoundsException);
		}

	}
}
