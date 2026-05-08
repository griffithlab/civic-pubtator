package db;
//
// https://bitbucket.org/xerial/sqlite-jdbc/downloads --> sqlite-jdbc-3.8.11.2.jar
// Add to build path
//

import java.io.BufferedReader;
import java.io.BufferedWriter;
import java.io.FileInputStream;
import java.io.FileOutputStream;
import java.io.FileReader;
import java.io.FileWriter;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.OutputStreamWriter;
import java.sql.*;
import java.util.HashMap;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;

public class DumpResult
{
	
	public static void Dump() throws IOException, InterruptedException, SQLException
	{
		
		try
		{
			Connection c = null;
			Statement stmt = null;
			try {
				Class.forName("org.sqlite.JDBC");
				c = DriverManager.getConnection("jdbc:sqlite:Database/gene2rs.db");
				stmt = c.createStatement();
				
				//System.out.println("Indexing");
				//stmt.executeUpdate("CREATE INDEX rs_index ON gene2rs (rs)");
				
				System.out.println("dump");
				BufferedWriter bw = new BufferedWriter(new OutputStreamWriter(new FileOutputStream("tmVarNormal.sql.rev"), "UTF-8"));
				BufferedReader br = new BufferedReader(new InputStreamReader(new FileInputStream("tmVarNormal.sql"), "UTF-8"));
				String line="";
				while ((line = br.readLine()) != null)  
				{
					String nt[]=line.split("\t");
					
					String pmid=nt[0];
					String type=nt[4];
					String RSs=nt[5];
					String mention=nt[6];
					
					Pattern pat = Pattern.compile(".*RS\\#\\:([0-9\\|]+)$");
					Matcher mat = pat.matcher(RSs);
					if(mat.find())
					{
						String RS[]=mat.group(1).split("\\|");
						String gene_offical="";
						String gene_Text="";
						
						for(int i=0;i<RS.length;i++)
						{
							String r=RS[i];
							
							ResultSet gene_id = stmt.executeQuery("SELECT gene FROM gene2rs WHERE rs like '%|"+r+"|%';");
							if ( gene_id.next() ) 
							{
								bw.write(pmid+"\t"+r+"\t"+mention+"\t"+gene_id.getString("gene")+"\t"+gene_offical+"\t"+gene_Text+"\n");
								System.out.println(pmid+"\t"+r+"\t"+mention+"\t"+gene_id.getString("gene")+"\t"+gene_offical+"\t"+gene_Text);
							}
							else
							{
								bw.write(pmid+"\t"+r+"\t"+mention+"\n");
								System.out.println(pmid+"\t"+r+"\t"+mention);
							}
						}
					}
				}
			} 
			catch ( Exception e ) 
			{
				System.err.println( e.getClass().getName() + ": " + e.getMessage() );
				System.exit(0);
			}
			stmt.close();
			c.close();
		}
		catch ( SQLException e ) 
		{
			System.out.println("Cannot connect database.");
		}
	}
	public static void main(String [] args) throws IOException, InterruptedException, SQLException, ClassNotFoundException 
	{
		Dump();
	}
}
