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

public class file2sqlslit_expired
{
	public static void CreateTable(String DBName,String TableName) throws IOException, InterruptedException
	{
		Connection c = null;
		Statement stmt = null;
		try {
			Class.forName("org.sqlite.JDBC");
			
			c = DriverManager.getConnection("jdbc:sqlite:"+DBName);
			stmt = c.createStatement();
			String sql = "CREATE TABLE "+TableName+" " +
			"(rs	CHAR(200)	NOT NULL  )"; 
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
	public static void Indexing(String DBName,String TableName,String index) throws IOException, InterruptedException
	{
		Connection c = null;
		Statement stmt = null;
		try {
			Class.forName("org.sqlite.JDBC");
			
			try {
				c = DriverManager.getConnection("jdbc:sqlite:"+DBName);
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
	public static void InsertRecord(String FileName,String DBName,String TableName) throws IOException, InterruptedException
	{
		Connection c = null;
		Statement stmt = null;
		try {
			Class.forName("org.sqlite.JDBC");
			c = DriverManager.getConnection("jdbc:sqlite:"+DBName);
			stmt = c.createStatement();
			
			BufferedReader br = new BufferedReader(new InputStreamReader(new FileInputStream(FileName), "UTF-8"));
			String line="";
			String sql="INSERT INTO "+TableName+" VALUES";
			int count=0;
			while ((line = br.readLine()) != null)  
			{
				if(count%1000==0)
				{
					sql=sql+"('"+line+"');";
					stmt.executeUpdate(sql);
					sql="INSERT INTO "+TableName+" VALUES";	   
				}
				else
				{
					sql=sql+"('"+line+"'),";
				}
				count++;
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
	public static void main(String [] args) throws IOException, InterruptedException, SQLException, ClassNotFoundException 
	{
		if(args.length<3)
		{
			System.out.println("$ java -Xmx5G -Xms5G -jar file2sqlslit_expired.jar CreateTable [DatabaseName] [TableName]\n");
			
			System.out.println("$ java -Xmx5G -Xms5G -jar file2sqlslit_expired.jar CreateTable Database/RegularlyUpdate/Expired.db Expired");
			System.out.println("$ java -Xmx5G -Xms5G -jar file2sqlslit_expired.jar InsertRecord Database/RegularlyUpdate/Expired.txt Database/RegularlyUpdate/Expired.db Expired\n");
			System.out.println("$ java -Xmx5G -Xms5G -jar file2sqlslit_expired.jar Indexing Database/RegularlyUpdate/Expired.db Expired rs\n");
			
			//System.out.println("CreateTable");
			//CreateTable("Database/RegularlyUpdate/Expired.db","Expired");
			
			//System.out.println("InsertRecord");
			//InsertRecord("Database/RegularlyUpdate/Expired.txt","Database/RegularlyUpdate/Expired.db","Expired");

			//System.out.println("Indexing");
			//Indexing("Database/RegularlyUpdate/Expired.db","Expired","rs");
		}
		else if (args[0].equals("CreateTable"))
		{
			String db= args[1];
			String table = args[2];
			CreateTable(db,table);
		}
		else if (args[0].equals("InsertRecord"))
		{
			String file = args[1];
			String db = args[2];
			String table = args[3];
			InsertRecord(file,db,table);
		}
		else if (args[0].equals("Indexing"))
		{
			String db= args[1];
			String table = args[2];
			String index = args[3];
			System.out.println("Indexing: "+db+"\t"+table+"\t"+index);
			Indexing(db,table,index);
		}
	}
}
