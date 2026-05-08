package db;
//
// https://bitbucket.org/xerial/sqlite-jdbc/downloads --> sqlite-jdbc-3.8.11.2.jar
// Add to build path
//

import java.io.BufferedReader;
import java.io.FileInputStream;
import java.io.FileReader;
import java.io.FileWriter;
import java.io.IOException;
import java.io.InputStreamReader;
import java.sql.*;
import java.util.HashMap;
import java.util.List;

public class file2sqlslit_chromosome
{
	public static void CreateTable_chromosome(String DBName,String TableName) throws IOException, InterruptedException
	{
		Connection c = null;
		Statement stmt = null;
		try {
			Class.forName("org.sqlite.JDBC");
			
			c = DriverManager.getConnection("jdbc:sqlite:"+DBName+".db");
			stmt = c.createStatement();
			String sql = "CREATE TABLE "+TableName+" " +
			"(rs	CHAR(20)	NOT NULL, " + 
			" chromosome	CHAR(5)	NOT NULL )"; 
			stmt.executeUpdate(sql);
			stmt.close();
			c.close();
		} 
		catch ( Exception e ) 
		{
			System.err.println( e.getClass().getName() + ": " + e.getMessage() );
			System.exit(0);
		}

	}
	public static void InsertRecord_chromosome(String FileName,String DBName,String TableName) throws IOException, InterruptedException
	{
		Connection c = null;
		Statement stmt = null;
		try {
			Class.forName("org.sqlite.JDBC");
			c = DriverManager.getConnection("jdbc:sqlite:"+DBName+".db");
			stmt = c.createStatement();
			
			BufferedReader br = new BufferedReader(new InputStreamReader(new FileInputStream(FileName), "UTF-8"));
			String line="";
			String sql="INSERT INTO "+TableName+" VALUES";
			int count=0;
			while ((line = br.readLine()) != null)  
			{
				String nt[]=line.split("\t");
				if(nt.length>1)
				{
					if(count%1000==0)
					{
						sql=sql+"('"+nt[0]+"','"+nt[1]+"');";
						stmt.executeUpdate(sql);
						sql="INSERT INTO "+TableName+" VALUES";	   
					}
					else
					{
						sql=sql+"('"+nt[0]+"','"+nt[1]+"'),";
					}
					count++;
				}
			}
			br.close();
			
			stmt.close();
			c.close();
		} 
		catch ( Exception e ) 
		{
			System.err.println( e.getClass().getName() + ": " + e.getMessage() );
			System.exit(0);
		}
	}
	public static void Indexing(String DBName,String TableName,String index) throws IOException, InterruptedException
	{
		Connection c = null;
		Statement stmt = null;
		try {
			Class.forName("org.sqlite.JDBC");
			
			try {
				c = DriverManager.getConnection("jdbc:sqlite:"+DBName+".db");
				stmt = c.createStatement();
				stmt.executeUpdate("CREATE INDEX "+TableName+"_index ON "+TableName+" ("+index+")");
				stmt.close();
				c.close();
			} 
			catch ( SQLException e ) 
			{
				System.err.println( e.getClass().getName() + ": " + e.getMessage() );
			}
		} 
		catch ( Exception e ) 
		{
			System.err.println( e.getClass().getName() + ": " + e.getMessage() );
			System.exit(0);
		}

	}
	public static void main(String [] args) throws IOException, InterruptedException, SQLException, ClassNotFoundException 
	{
		System.out.println("CreateTable");
		CreateTable_chromosome("rs2chromosome","rs2chromosome");
		System.out.println("InsertRecord");
		InsertRecord_chromosome("rs2chromosome.txt","rs2chromosome","rs2chromosome");
		System.out.println("Indexing");
		Indexing("rs2chromosome","rs2chromosome","rs");
	}
}
