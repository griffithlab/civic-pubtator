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

public class select
{
	
	public static void search_location(String Variationlocation,String VariationDB,String VariationGene) throws IOException, InterruptedException, SQLException
	{
		try
		{
			/*
			 * 1354 1000
			 * 146406	100000
			 * 293384	200000
			 */
			///*
			String var2rs="";
			{
				Connection c = null;
				Statement stmt = null;
				try {
					Class.forName("org.sqlite.JDBC");
				} 
				catch ( Exception e ) 
				{
					System.err.println( e.getClass().getName() + ": " + e.getMessage() );
					System.exit(0);
				}
				c = DriverManager.getConnection("jdbc:sqlite:Database/"+VariationDB+".db");
				stmt = c.createStatement();
				String SQL="SELECT rs FROM "+VariationDB+" WHERE var like '%"+Variationlocation+"%'";
				System.out.println(SQL);
				ResultSet rs = stmt.executeQuery(SQL);
				while ( rs.next() ) 
				{
					//System.out.println("prefix : "+rs.getString("prefix"));
					if(var2rs.equals(""))
					{
						var2rs=rs.getString("rs");
					}
					else
					{
						var2rs=var2rs+"|"+rs.getString("rs");
					}
				}
				stmt.close();
				c.close();
				
			}
			System.out.println("Variation : "+var2rs);
			//*/
			
			/*
			 * Count the average rs number per gene
			 * 10000 genes : 1757 rs 
			 * 100000 genes : 2549 rs
			 * 200000 genes : 2549 rs
			 * 300000 genes : 2286 rs
 			 */
			///*
			String gene2rs="";
			{
				HashMap<String,String> RSs = new HashMap<String,String>();
				Connection c = DriverManager.getConnection("jdbc:sqlite:Database/gene2rs.db");
				Statement stmt = c.createStatement();
				String SQL="SELECT rs FROM gene2rs where gene='"+VariationGene+"'";
				System.out.println(SQL);
				ResultSet rs = stmt.executeQuery(SQL);
				while ( rs.next() ) 
				{
					System.out.println("gene Variation : "+rs.getString("rs"));
					gene2rs=rs.getString("rs");
				}
				stmt.close();
				c.close();
			}
			//*/
			
			System.out.println("Overlap:");
			String var2rs_Arr[]=var2rs.split("\\|");
			String gene2rs_Arr[]=gene2rs.split("\\|");
			for(int i=0;i<var2rs_Arr.length;i++)
			{
				for(int j=0;j<gene2rs_Arr.length;j++)
				{
					//System.out.println(var2rs_Arr[i]+"\t"+gene2rs_Arr[i]);
					if(var2rs_Arr[i].equals(gene2rs_Arr[j]))
					{
						System.out.println(var2rs_Arr[i]);
					}
					
				}
			}
		}
		catch ( SQLException e ) 
		{
			System.out.println("Cannot connect database.");
		}
	}
	public static void search(String VariationMention,String VariationDB,String VariationTable,String VariationGene) throws IOException, InterruptedException, SQLException
	{
		try
		{
			/*
			 * 1354 1000
			 * 146406	100000
			 * 293384	200000
			 */
			///*
			String var2rs="";
			{
				Connection c = null;
				Statement stmt = null;
				try {
					Class.forName("org.sqlite.JDBC");
				} 
				catch ( Exception e ) 
				{
					System.err.println( e.getClass().getName() + ": " + e.getMessage() );
					System.exit(0);
				}
				c = DriverManager.getConnection("jdbc:sqlite:Database/"+VariationDB+".db");
				stmt = c.createStatement();
				String SQL="SELECT rs FROM "+VariationTable+" WHERE var='"+VariationMention+"'";
				System.out.println(SQL);
				ResultSet rs = stmt.executeQuery(SQL);
				while ( rs.next() ) 
				{
					System.out.println("Variation : "+rs.getString("rs"));
					var2rs=rs.getString("rs");
				}
				stmt.close();
				c.close();
				
			}
			//*/
			
			/*
			 * Count the average rs number per gene
			 * 10000 genes : 1757 rs 
			 * 100000 genes : 2549 rs
			 * 200000 genes : 2549 rs
			 * 300000 genes : 2286 rs
 			 */
			///*
			String gene2rs="";
			{
				HashMap<String,String> RSs = new HashMap<String,String>();
				Connection c = DriverManager.getConnection("jdbc:sqlite:Database/gene2rs.db");
				Statement stmt = c.createStatement();
				String SQL="SELECT rs FROM gene2rs where gene='"+VariationGene+"'";
				//System.out.println(SQL);
				ResultSet rs = stmt.executeQuery(SQL);
				while ( rs.next() ) 
				{
					//System.out.println("gene Variation : "+rs.getString("rs"));
					gene2rs=rs.getString("rs");
				}
				stmt.close();
				c.close();
			}
			//*/
			
			
			String var2rs_Arr[]=var2rs.split("\\|");
			String gene2rs_Arr[]=gene2rs.split("\\|");
			for(int i=0;i<var2rs_Arr.length;i++)
			{
				for(int j=0;j<gene2rs_Arr.length;j++)
				{
					//System.out.println(var2rs_Arr[i]+"\t"+gene2rs_Arr[i]);
					if(var2rs_Arr[i].equals(gene2rs_Arr[j]))
					{
						System.out.println(VariationMention+"\t"+VariationDB+"\t"+VariationGene+":"+var2rs_Arr[i]);
					}
					
				}
			}
		}
		catch ( SQLException e ) 
		{
			System.out.println("Cannot connect database.");
		}
	}
	public static void main(String [] args) throws IOException, InterruptedException, SQLException, ClassNotFoundException 
	{
		/*
		String filename="train.Curated.pair.txt";
		
		BufferedReader PAM = new BufferedReader(new InputStreamReader(new FileInputStream(filename), "UTF-8"));
		String line="";
		while ((line = PAM.readLine()) != null)  
		{
			String nt[]=line.split("\t");
			
			String VariationMention=nt[1];
			String VariationMention_org=nt[2];
			String VariationDB=nt[0];
			String VariationGene=nt[3];
			search(VariationMention,VariationDB,VariationGene);
			search(VariationMention_org,VariationDB,VariationGene);
		}
		PAM.close();
		*/
		/*
		String VariationDB="var2rs_c";
		String VariationGene="78987";
		search(VariationMention,VariationDB,VariationGene);
		*/
		String VariationMention="p.Asp2267Asn";
		String VariationDB="var2rs_clinvar_proteinchange.old";
		String VariationTable="var2rs_clinvar_proteinchange";
		String VariationGene="8878";
		search(VariationMention,VariationDB,VariationTable,VariationGene);
		
		System.exit(0);
		
		if(args.length<2)
		{
			System.out.println("\n$ java -Xmx5G -Xms5G -jar select.jar [VariationMention] [VariationDB] [VariationGene]");
			System.out.println("\n$ java -Xmx5G -Xms5G -jar select.jar c.857C>G var2rs_c 78987");
			
			
		}
		else
		{
			//String VariationMention=args[0];
			//String VariationDB=args[1];
			//String VariationGene=args[2];
			System.out.println(VariationMention+"\t"+VariationDB+"\t"+VariationGene);
			search(VariationMention,VariationDB,VariationTable,VariationGene);
		}
	}
}
