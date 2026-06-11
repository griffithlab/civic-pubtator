package ncbi.taggerOne.util.vector;

import static org.junit.Assert.*;

import java.util.HashMap;
import java.util.Map;

import ncbi.taggerOne.T1Constants;
import ncbi.taggerOne.util.Dictionary;
import ncbi.taggerOne.util.vector.Vector.VectorIterator;

import org.junit.Assert;
import org.junit.Test;

public class VectorTest {

	@Test
	public void testDense() {
		VectorFactory factory = DenseVector.factory;
		testBasic1(factory);
		testBasic2(factory);
		testExceptions(factory);
		testIncrement1(factory);
		testIncrement2(factory, DenseVector.factory);
		testIncrement2(factory, SparseVector.factory);
		testIncrement3(factory, DenseVector.factory);
		testIncrement3(factory, SparseVector.factory);
		testDotProduct(factory, DenseVector.factory);
		testDotProduct(factory, SparseVector.factory);
		testNormalize(factory);
		testCopy(factory);
		testEquals(factory);
		testHashCode(factory);
	}

	@Test
	public void testSparse() {
		VectorFactory factory = SparseVector.factory;
		testBasic1(factory);
		testBasic2(factory);
		testExceptions(factory);
		testIncrement1(factory);
		testIncrement2(factory, DenseVector.factory);
		testIncrement2(factory, SparseVector.factory);
		testIncrement3(factory, DenseVector.factory);
		testIncrement3(factory, SparseVector.factory);
		testDotProduct(factory, DenseVector.factory);
		testDotProduct(factory, SparseVector.factory);
		testNormalize(factory);
		testCopy(factory);
		testEquals(factory);
		testHashCode(factory);
	}

	@Test
	public void testCardinality() {
		Dictionary<String> d = getDictionary(1000);
		Vector<String> dv = DenseVector.factory.create(d);
		Vector<String> sv = SparseVector.factory.create(d);

		assertEquals(1000, dv.cardinality());
		assertEquals(0, sv.cardinality());

		int[] indices = { 693, 192, 59, 0, 133, 934, 15, 856, 444, 349, 999, 649, 112 };

		for (int i = 0; i < indices.length; i++) {
			assertEquals(1000, dv.cardinality());
			assertEquals(i, sv.cardinality());

			dv.set(i, 1.0);
			sv.set(i, 1.0);
		}

		assertEquals(1000, dv.cardinality());
		assertEquals(indices.length, sv.cardinality());
	}

	private static void testBasic1(VectorFactory factory) {
		Dictionary<String> d = getDictionary(5);
		Vector<String> v = factory.create(d);
		assertEquals(d, v.getDictionary());
		Map<Integer, Double> values = new HashMap<Integer, Double>();

		assertEquals(5, v.dimensions());
		assertTrue(v.isEmpty());
		assertEquals(0.0, v.get(0), T1Constants.EPSILON);
		assertEquals(0.0, v.get(1), T1Constants.EPSILON);
		assertEquals(0.0, v.get(2), T1Constants.EPSILON);
		assertEquals(0.0, v.get(3), T1Constants.EPSILON);
		assertEquals(0.0, v.get(4), T1Constants.EPSILON);
		checkIterator(v, values);
		assertEquals(0.0, v.length(), T1Constants.EPSILON);
		assertEquals("[]", v.visualize());

		v.set(0, 1.0);
		values.put(0, 1.0);

		assertEquals(5, v.dimensions());
		assertEquals(1, values.size());
		assertFalse(v.isEmpty());
		assertEquals(1.0, v.get(0), T1Constants.EPSILON);
		assertEquals(0.0, v.get(1), T1Constants.EPSILON);
		assertEquals(0.0, v.get(2), T1Constants.EPSILON);
		assertEquals(0.0, v.get(3), T1Constants.EPSILON);
		assertEquals(0.0, v.get(4), T1Constants.EPSILON);
		checkIterator(v, values);
		assertEquals(1.0, v.length(), T1Constants.EPSILON);
		assertEquals("[0:e0=1.0]", v.visualize());

		v.set(1, 2.0);
		values.put(1, 2.0);

		assertEquals(5, v.dimensions());
		assertEquals(2, values.size());
		assertFalse(v.isEmpty());
		assertEquals(1.0, v.get(0), T1Constants.EPSILON);
		assertEquals(2.0, v.get(1), T1Constants.EPSILON);
		assertEquals(0.0, v.get(2), T1Constants.EPSILON);
		assertEquals(0.0, v.get(3), T1Constants.EPSILON);
		assertEquals(0.0, v.get(4), T1Constants.EPSILON);
		checkIterator(v, values);
		assertEquals(Math.sqrt(5.0), v.length(), T1Constants.EPSILON);
		assertEquals("[0:e0=1.0, 1:e1=2.0]", v.visualize());

		v.set(2, 3.0);
		values.put(2, 3.0);

		assertEquals(5, v.dimensions());
		assertEquals(3, values.size());
		assertFalse(v.isEmpty());
		assertEquals(1.0, v.get(0), T1Constants.EPSILON);
		assertEquals(2.0, v.get(1), T1Constants.EPSILON);
		assertEquals(3.0, v.get(2), T1Constants.EPSILON);
		assertEquals(0.0, v.get(3), T1Constants.EPSILON);
		assertEquals(0.0, v.get(4), T1Constants.EPSILON);
		checkIterator(v, values);
		assertEquals(Math.sqrt(14.0), v.length(), T1Constants.EPSILON);
		assertEquals("[0:e0=1.0, 1:e1=2.0, 2:e2=3.0]", v.visualize());

		v.set(3, 4.0);
		values.put(3, 4.0);

		assertEquals(5, v.dimensions());
		assertEquals(4, values.size());
		assertFalse(v.isEmpty());
		assertEquals(1.0, v.get(0), T1Constants.EPSILON);
		assertEquals(2.0, v.get(1), T1Constants.EPSILON);
		assertEquals(3.0, v.get(2), T1Constants.EPSILON);
		assertEquals(4.0, v.get(3), T1Constants.EPSILON);
		assertEquals(0.0, v.get(4), T1Constants.EPSILON);
		checkIterator(v, values);
		assertEquals(Math.sqrt(30.0), v.length(), T1Constants.EPSILON);
		assertEquals("[0:e0=1.0, 1:e1=2.0, 2:e2=3.0, 3:e3=4.0]", v.visualize());

		v.set(4, 5.0);
		values.put(4, 5.0);

		assertEquals(5, v.dimensions());
		assertEquals(5, values.size());
		assertFalse(v.isEmpty());
		assertEquals(1.0, v.get(0), T1Constants.EPSILON);
		assertEquals(2.0, v.get(1), T1Constants.EPSILON);
		assertEquals(3.0, v.get(2), T1Constants.EPSILON);
		assertEquals(4.0, v.get(3), T1Constants.EPSILON);
		assertEquals(5.0, v.get(4), T1Constants.EPSILON);
		checkIterator(v, values);
		assertEquals(Math.sqrt(55.0), v.length(), T1Constants.EPSILON);
		assertEquals("[0:e0=1.0, 1:e1=2.0, 2:e2=3.0, 3:e3=4.0, 4:e4=5.0]", v.visualize());

		v.set(0, 6.0);
		values.put(0, 6.0);

		assertEquals(5, v.dimensions());
		assertEquals(5, values.size());
		assertFalse(v.isEmpty());
		assertEquals(6.0, v.get(0), T1Constants.EPSILON);
		assertEquals(2.0, v.get(1), T1Constants.EPSILON);
		assertEquals(3.0, v.get(2), T1Constants.EPSILON);
		assertEquals(4.0, v.get(3), T1Constants.EPSILON);
		assertEquals(5.0, v.get(4), T1Constants.EPSILON);
		checkIterator(v, values);
		assertEquals(Math.sqrt(90.0), v.length(), T1Constants.EPSILON);
		assertEquals("[0:e0=6.0, 1:e1=2.0, 2:e2=3.0, 3:e3=4.0, 4:e4=5.0]", v.visualize());

		v.set(1, 0.0);
		values.remove(1);

		assertEquals(5, v.dimensions());
		assertEquals(4, values.size());
		assertFalse(v.isEmpty());
		assertEquals(6.0, v.get(0), T1Constants.EPSILON);
		assertEquals(0.0, v.get(1), T1Constants.EPSILON);
		assertEquals(3.0, v.get(2), T1Constants.EPSILON);
		assertEquals(4.0, v.get(3), T1Constants.EPSILON);
		assertEquals(5.0, v.get(4), T1Constants.EPSILON);
		checkIterator(v, values);
		assertEquals(Math.sqrt(86.0), v.length(), T1Constants.EPSILON);
		assertEquals("[0:e0=6.0, 2:e2=3.0, 3:e3=4.0, 4:e4=5.0]", v.visualize());
	}

	private static void testBasic2(VectorFactory factory) {
		Dictionary<String> d = getDictionary(100);
		Vector<String> v = factory.create(d);
		assertEquals(d, v.getDictionary());
		Map<Integer, Double> values = new HashMap<Integer, Double>();

		assertEquals(100, v.dimensions());
		assertTrue(v.isEmpty());
		checkIterator(v, values);
		assertEquals(0.0, v.length(), T1Constants.EPSILON);

		v.set(74, 0.78);
		values.put(74, 0.78);

		assertEquals(100, v.dimensions());
		assertEquals(1, values.size());
		assertFalse(v.isEmpty());
		assertEquals(0.78, v.get(74), T1Constants.EPSILON);
		checkIterator(v, values);
		assertEquals(Math.sqrt(0.6084), v.length(), T1Constants.EPSILON);

		v.set(91, 0.66);
		values.put(91, 0.66);

		assertEquals(100, v.dimensions());
		assertEquals(2, values.size());
		assertFalse(v.isEmpty());
		assertEquals(0.78, v.get(74), T1Constants.EPSILON);
		assertEquals(0.66, v.get(91), T1Constants.EPSILON);
		checkIterator(v, values);
		assertEquals(Math.sqrt(1.044), v.length(), T1Constants.EPSILON);

		v.set(26, 0.23);
		values.put(26, 0.23);

		assertEquals(100, v.dimensions());
		assertEquals(3, values.size());
		assertFalse(v.isEmpty());
		assertEquals(0.23, v.get(26), T1Constants.EPSILON);
		assertEquals(0.78, v.get(74), T1Constants.EPSILON);
		assertEquals(0.66, v.get(91), T1Constants.EPSILON);
		checkIterator(v, values);
		assertEquals(Math.sqrt(1.0969), v.length(), T1Constants.EPSILON);

		v.set(66, 0.08);
		values.put(66, 0.08);

		assertEquals(100, v.dimensions());
		assertEquals(4, values.size());
		assertFalse(v.isEmpty());
		assertEquals(0.23, v.get(26), T1Constants.EPSILON);
		assertEquals(0.08, v.get(66), T1Constants.EPSILON);
		assertEquals(0.78, v.get(74), T1Constants.EPSILON);
		assertEquals(0.66, v.get(91), T1Constants.EPSILON);
		checkIterator(v, values);
		assertEquals(Math.sqrt(1.1033), v.length(), T1Constants.EPSILON);

		v.set(83, 0.60);
		values.put(83, 0.60);

		assertEquals(100, v.dimensions());
		assertEquals(5, values.size());
		assertFalse(v.isEmpty());
		assertEquals(0.23, v.get(26), T1Constants.EPSILON);
		assertEquals(0.08, v.get(66), T1Constants.EPSILON);
		assertEquals(0.78, v.get(74), T1Constants.EPSILON);
		assertEquals(0.60, v.get(83), T1Constants.EPSILON);
		assertEquals(0.66, v.get(91), T1Constants.EPSILON);
		checkIterator(v, values);
		assertEquals(Math.sqrt(1.4633), v.length(), T1Constants.EPSILON);

		v.set(83, 0.42);
		values.put(83, 0.42);

		assertEquals(100, v.dimensions());
		assertEquals(5, values.size());
		assertFalse(v.isEmpty());
		assertEquals(0.23, v.get(26), T1Constants.EPSILON);
		assertEquals(0.08, v.get(66), T1Constants.EPSILON);
		assertEquals(0.78, v.get(74), T1Constants.EPSILON);
		assertEquals(0.42, v.get(83), T1Constants.EPSILON);
		assertEquals(0.66, v.get(91), T1Constants.EPSILON);
		checkIterator(v, values);
		assertEquals(Math.sqrt(1.2797), v.length(), T1Constants.EPSILON);

		v.set(74, 0.0);
		values.remove(74);

		assertEquals(100, v.dimensions());
		assertEquals(4, values.size());
		assertFalse(v.isEmpty());
		assertEquals(0.23, v.get(26), T1Constants.EPSILON);
		assertEquals(0.08, v.get(66), T1Constants.EPSILON);
		assertEquals(0.0, v.get(74), T1Constants.EPSILON);
		assertEquals(0.42, v.get(83), T1Constants.EPSILON);
		assertEquals(0.66, v.get(91), T1Constants.EPSILON);
		checkIterator(v, values);
		assertEquals(Math.sqrt(0.6713), v.length(), T1Constants.EPSILON);

	}

	private static void testExceptions(VectorFactory factory) {
		// Null dictionary
		Dictionary<String> d = null;
		try {
			factory.create(d);
			Assert.fail("Expected exception to be thrown");
		} catch (Exception e) {
			assertTrue(e instanceof IllegalArgumentException);
		}
		// Dictionary not frozen
		d = new Dictionary<String>();
		assertFalse(d.isFrozen());
		try {
			factory.create(d);
			Assert.fail("Expected exception to be thrown");
		} catch (Exception e) {
			assertTrue(e instanceof IllegalArgumentException);
		}
		// Get index < 0
		d = getDictionary(5);
		Vector<String> v = factory.create(d);
		try {
			v.get(-1);
			Assert.fail("Expected exception to be thrown");
		} catch (Exception e) {
			assertTrue(e instanceof IndexOutOfBoundsException);
		}
		// Get index == size
		try {
			v.get(5);
			Assert.fail("Expected exception to be thrown");
		} catch (Exception e) {
			assertTrue(e instanceof IndexOutOfBoundsException);
		}
		// Get index > size
		try {
			v.get(10);
			Assert.fail("Expected exception to be thrown");
		} catch (Exception e) {
			assertTrue(e instanceof IndexOutOfBoundsException);
		}
		// Set index < 0
		try {
			v.set(-1, 1.0);
			Assert.fail("Expected exception to be thrown");
		} catch (Exception e) {
			assertTrue(e instanceof IndexOutOfBoundsException);
		}
		// Set index == size
		try {
			v.set(5, 1.0);
			Assert.fail("Expected exception to be thrown");
		} catch (Exception e) {
			assertTrue(e instanceof IndexOutOfBoundsException);
		}
		// Set index > size
		try {
			v.set(10, 1.0);
			Assert.fail("Expected exception to be thrown");
		} catch (Exception e) {
			assertTrue(e instanceof IndexOutOfBoundsException);
		}
		// Increment index < 0
		try {
			v.increment(-1, 1.0);
			Assert.fail("Expected exception to be thrown");
		} catch (Exception e) {
			assertTrue(e instanceof IndexOutOfBoundsException);
		}
		// Increment index == size
		try {
			v.increment(5, 1.0);
			Assert.fail("Expected exception to be thrown");
		} catch (Exception e) {
			assertTrue(e instanceof IndexOutOfBoundsException);
		}
		// Increment index > size
		try {
			v.increment(10, 1.0);
			Assert.fail("Expected exception to be thrown");
		} catch (Exception e) {
			assertTrue(e instanceof IndexOutOfBoundsException);
		}
		Vector<String> v2 = factory.create(getDictionary(10));
		try {
			v.increment(v2);
			Assert.fail("Expected exception to be thrown");
		} catch (Exception e) {
			assertTrue(e instanceof IllegalArgumentException);
		}
		try {
			v.increment(2.0, v2);
			Assert.fail("Expected exception to be thrown");
		} catch (Exception e) {
			assertTrue(e instanceof IllegalArgumentException);
		}
		try {
			v.dotProduct(v2);
			Assert.fail("Expected exception to be thrown");
		} catch (Exception e) {
			assertTrue(e instanceof IllegalArgumentException);
		}
	}

	private static void testIncrement1(VectorFactory factory) {
		Dictionary<String> d = getDictionary(1000);
		Vector<String> v = factory.create(d);
		assertEquals(d, v.getDictionary());
		Map<Integer, Double> values = new HashMap<Integer, Double>();

		assertEquals(1000, v.dimensions());
		assertTrue(v.isEmpty());
		checkIterator(v, values);
		assertEquals(0.0, v.length(), T1Constants.EPSILON);

		v.increment(671, 0.1);
		v.increment(239, 0.2);
		v.increment(568, 0.3);
		v.increment(978, 0.4);
		v.increment(325, 0.5);
		values.put(671, 0.1);
		values.put(239, 0.2);
		values.put(568, 0.3);
		values.put(978, 0.4);
		values.put(325, 0.5);

		assertEquals(1000, v.dimensions());
		assertFalse(v.isEmpty());
		assertEquals(0.1, v.get(671), T1Constants.EPSILON);
		assertEquals(0.2, v.get(239), T1Constants.EPSILON);
		assertEquals(0.3, v.get(568), T1Constants.EPSILON);
		assertEquals(0.4, v.get(978), T1Constants.EPSILON);
		assertEquals(0.5, v.get(325), T1Constants.EPSILON);
		checkIterator(v, values);
		assertEquals(Math.sqrt(0.55), v.length(), T1Constants.EPSILON);

		v.increment(671, 0.6);
		v.increment(239, 0.7);
		v.increment(568, 0.8);
		v.increment(978, 0.9);
		v.increment(325, 1.0);
		values.put(671, 0.7);
		values.put(239, 0.9);
		values.put(568, 1.1);
		values.put(978, 1.3);
		values.put(325, 1.5);

		assertEquals(1000, v.dimensions());
		assertFalse(v.isEmpty());
		assertEquals(0.7, v.get(671), T1Constants.EPSILON);
		assertEquals(0.9, v.get(239), T1Constants.EPSILON);
		assertEquals(1.1, v.get(568), T1Constants.EPSILON);
		assertEquals(1.3, v.get(978), T1Constants.EPSILON);
		assertEquals(1.5, v.get(325), T1Constants.EPSILON);
		checkIterator(v, values);
		assertEquals(Math.sqrt(6.45), v.length(), T1Constants.EPSILON);
	}

	private static void testIncrement2(VectorFactory factory1, VectorFactory factory2) {
		Dictionary<String> d = getDictionary(1000);
		Vector<String> v1 = factory1.create(d);
		Vector<String> v2 = factory2.create(d);
		Map<Integer, Double> values = new HashMap<Integer, Double>();

		assertEquals(1000, v1.dimensions());
		assertTrue(v1.isEmpty());
		checkIterator(v1, values);
		assertEquals(0.0, v1.length(), T1Constants.EPSILON);

		v2.increment(189, 0.0);
		v2.increment(671, 0.1);
		v2.increment(239, 0.2);
		v2.increment(568, 0.3);
		v2.increment(978, 0.4);
		v2.increment(325, 0.5);
		values.put(671, 0.1);
		values.put(239, 0.2);
		values.put(568, 0.3);
		values.put(978, 0.4);
		values.put(325, 0.5);
		v1.increment(v2);

		assertEquals(1000, v1.dimensions());
		assertFalse(v1.isEmpty());
		assertEquals(0.1, v1.get(671), T1Constants.EPSILON);
		assertEquals(0.2, v1.get(239), T1Constants.EPSILON);
		assertEquals(0.3, v1.get(568), T1Constants.EPSILON);
		assertEquals(0.4, v1.get(978), T1Constants.EPSILON);
		assertEquals(0.5, v1.get(325), T1Constants.EPSILON);
		checkIterator(v1, values);
		assertEquals(Math.sqrt(0.55), v1.length(), T1Constants.EPSILON);

		v2 = factory2.create(d);
		v2.increment(189, 0.0);
		v2.increment(671, 0.6);
		v2.increment(239, 0.7);
		v2.increment(568, 0.8);
		v2.increment(978, 0.9);
		v2.increment(325, 1.0);
		values.put(671, 0.7);
		values.put(239, 0.9);
		values.put(568, 1.1);
		values.put(978, 1.3);
		values.put(325, 1.5);
		v1.increment(v2);

		assertEquals(1000, v1.dimensions());
		assertFalse(v1.isEmpty());
		assertEquals(0.7, v1.get(671), T1Constants.EPSILON);
		assertEquals(0.9, v1.get(239), T1Constants.EPSILON);
		assertEquals(1.1, v1.get(568), T1Constants.EPSILON);
		assertEquals(1.3, v1.get(978), T1Constants.EPSILON);
		assertEquals(1.5, v1.get(325), T1Constants.EPSILON);
		checkIterator(v1, values);
		assertEquals(Math.sqrt(6.45), v1.length(), T1Constants.EPSILON);
	}

	private static void testIncrement3(VectorFactory factory1, VectorFactory factory2) {
		Dictionary<String> d = getDictionary(1000);
		Vector<String> v1 = factory1.create(d);
		Vector<String> v2 = factory2.create(d);
		Map<Integer, Double> values = new HashMap<Integer, Double>();

		assertEquals(1000, v1.dimensions());
		assertTrue(v1.isEmpty());
		checkIterator(v1, values);
		assertEquals(0.0, v1.length(), T1Constants.EPSILON);

		v2.increment(671, 0.1);
		v2.increment(239, 0.2);
		v2.increment(568, 0.3);
		v2.increment(978, 0.4);
		v2.increment(325, 0.5);
		values.put(671, 0.3);
		values.put(239, 0.6);
		values.put(568, 0.9);
		values.put(978, 1.2);
		values.put(325, 1.5);
		v1.increment(3.0, v2);

		assertEquals(1000, v1.dimensions());
		assertFalse(v1.isEmpty());
		assertEquals(0.3, v1.get(671), T1Constants.EPSILON);
		assertEquals(0.6, v1.get(239), T1Constants.EPSILON);
		assertEquals(0.9, v1.get(568), T1Constants.EPSILON);
		assertEquals(1.2, v1.get(978), T1Constants.EPSILON);
		assertEquals(1.5, v1.get(325), T1Constants.EPSILON);
		checkIterator(v1, values);
		assertEquals(Math.sqrt(4.95), v1.length(), T1Constants.EPSILON);

		v2 = factory2.create(d);
		v2.increment(671, 0.6);
		v2.increment(239, 0.7);
		v2.increment(568, 0.8);
		v2.increment(978, 0.9);
		v2.increment(325, 1.0);
		values.put(671, 1.5);
		values.put(239, 2.0);
		values.put(568, 2.5);
		values.put(978, 3.0);
		values.put(325, 3.5);
		v1.increment(2.0, v2);

		assertEquals(1000, v1.dimensions());
		assertFalse(v1.isEmpty());
		assertEquals(1.5, v1.get(671), T1Constants.EPSILON);
		assertEquals(2.0, v1.get(239), T1Constants.EPSILON);
		assertEquals(2.5, v1.get(568), T1Constants.EPSILON);
		assertEquals(3.0, v1.get(978), T1Constants.EPSILON);
		assertEquals(3.5, v1.get(325), T1Constants.EPSILON);
		checkIterator(v1, values);
		assertEquals(Math.sqrt(33.75), v1.length(), T1Constants.EPSILON);
	}

	private static void testDotProduct(VectorFactory factory1, VectorFactory factory2) {
		Dictionary<String> d = getDictionary(1000);
		Vector<String> v1 = factory1.create(d);
		Vector<String> v2 = factory2.create(d);

		v1.set(170, 0.56);
		v1.set(9, 0.15);
		v1.set(364, 0.23);
		v1.set(839, 0.48);
		v2.set(9, 0.96);
		v2.set(364, 0.26);
		v2.set(993, 0.76);
		v2.set(839, 0.51);

		assertEquals(0.4486, v1.dotProduct(v2), T1Constants.EPSILON);
		assertEquals(0.4486, v2.dotProduct(v1), T1Constants.EPSILON);
	}

	private static void testNormalize(VectorFactory factory) {
		Dictionary<String> d = getDictionary(1000);
		Vector<String> v1 = factory.create(d);

		v1.set(170, 0.56);
		v1.set(9, 0.15);
		v1.set(364, 0.23);
		v1.set(839, 0.48);
		v1.set(993, 0.76);

		assertEquals(0.56, v1.get(170), T1Constants.EPSILON);
		assertEquals(0.15, v1.get(9), T1Constants.EPSILON);
		assertEquals(0.23, v1.get(364), T1Constants.EPSILON);
		assertEquals(0.48, v1.get(839), T1Constants.EPSILON);
		assertEquals(0.76, v1.get(993), T1Constants.EPSILON);
		double len = Math.sqrt(1.197);
		assertEquals(len, v1.length(), T1Constants.EPSILON);

		v1.normalize();

		assertEquals(0.56 / len, v1.get(170), T1Constants.EPSILON);
		assertEquals(0.15 / len, v1.get(9), T1Constants.EPSILON);
		assertEquals(0.23 / len, v1.get(364), T1Constants.EPSILON);
		assertEquals(0.48 / len, v1.get(839), T1Constants.EPSILON);
		assertEquals(0.76 / len, v1.get(993), T1Constants.EPSILON);
		assertEquals(1.0, v1.length(), T1Constants.EPSILON);
	}

	private static void testCopy(VectorFactory factory) {
		Dictionary<String> d = getDictionary(2);
		Vector<String> v1 = factory.create(d);
		v1.set(0, 0.63);
		v1.set(1, 0.86);
		Vector<String> v2 = v1.copy();

		assertEquals(0.63, v1.get(0), T1Constants.EPSILON);
		assertEquals(0.86, v1.get(1), T1Constants.EPSILON);
		assertEquals(0.63, v2.get(0), T1Constants.EPSILON);
		assertEquals(0.86, v2.get(1), T1Constants.EPSILON);

		v2.set(0, 0.36);
		v2.set(1, 0.44);

		assertEquals(0.63, v1.get(0), T1Constants.EPSILON);
		assertEquals(0.86, v1.get(1), T1Constants.EPSILON);
		assertEquals(0.36, v2.get(0), T1Constants.EPSILON);
		assertEquals(0.44, v2.get(1), T1Constants.EPSILON);

	}

	private static void testEquals(VectorFactory factory) {
		Dictionary<String> d = getDictionary(3);
		Vector<String> v1 = factory.create(d);
		v1.set(1, 0.59);
		v1.set(2, 0.81);
		assertTrue(v1.equals(v1));
		assertFalse(v1.equals(null));
		assertFalse(v1.equals("string"));

		Vector<String> v2 = factory.create(d);
		v2.set(1, 0.59);
		v2.set(2, 0.81);
		assertTrue(v1.equals(v2));
		assertTrue(v2.equals(v1));

		Vector<String> v3 = factory.create(d);
		v3.set(1, 0.59);
		v3.set(2, 0.17);
		assertFalse(v1.equals(v3));
		assertFalse(v3.equals(v1));

		Vector<String> v4 = factory.create(getDictionary(4));
		assertFalse(v1.equals(v4));
		assertFalse(v4.equals(v1));

		Vector<String> v5 = factory.create(d);
		assertFalse(v1.equals(v5));
		assertFalse(v5.equals(v1));

		Vector<String> v6 = factory.create(d);
		v6.set(2, 0.81);
		assertFalse(v1.equals(v6));
		assertFalse(v6.equals(v1));

		Vector<String> v7 = factory.create(d);
		v7.set(0, 0.36);
		v7.set(2, 0.81);
		assertFalse(v1.equals(v7));
		assertFalse(v7.equals(v1));
	}

	private static void testHashCode(VectorFactory factory) {
		Dictionary<String> d = getDictionary(3);

		Vector<String> v1a = factory.create(d);
		v1a.set(1, 0.59);
		v1a.set(2, 0.81);
		Vector<String> v1b = factory.create(d);
		v1b.set(1, 0.59);
		v1b.set(2, 0.81);
		Vector<String> v2a = factory.create(d);
		v2a.set(0, 0.59);
		v2a.set(2, 0.81);
		Vector<String> v2b = factory.create(d);
		v2b.set(0, 0.59);
		v2b.set(2, 0.81);

		assertTrue(v1a.hashCode() == v1b.hashCode());
		assertTrue(v2a.hashCode() == v2b.hashCode());
		assertFalse(v1a.hashCode() == v2a.hashCode());
		assertFalse(v1b.hashCode() == v2b.hashCode());
	}

	private static Dictionary<String> getDictionary(int size) {
		Dictionary<String> dict = new Dictionary<String>();
		for (int i = 0; i < size; i++) {
			dict.addElement("e" + i);
		}
		dict.freeze();
		return dict;
	}

	private static void checkIterator(Vector<String> vector, Map<Integer, Double> values) {
		Map<Integer, Double> valuesCopy = new HashMap<Integer, Double>(values);
		VectorIterator iterator = vector.getIterator();
		while (iterator.next()) {
			int index = iterator.getIndex();
			double value = iterator.getValue();
			assertTrue("iterator should not contain a nonzero value for index = " + index + " value = " + value, valuesCopy.containsKey(index));
			double value2 = valuesCopy.get(index);
			assertEquals(value2, value, T1Constants.EPSILON);
			valuesCopy.remove(index);
		}
		assertTrue(valuesCopy.isEmpty());
	}

}
