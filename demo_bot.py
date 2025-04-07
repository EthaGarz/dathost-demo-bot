from botocore.client import Config
from botocore.exceptions import ClientError
from discord import app_commands
from dotenv import load_dotenv
import discord
import asyncio
import aioboto3
import re
import os
load_dotenv()

secret = os.getenv("pass")
host_email = os.getenv("host_email")
user_email = os.getenv("user_email")
api = os.getenv("discord_demo_bot")
bucket = os.getenv("bucket")
region = os.getenv("region")
aws_access_key = os.getenv("ACCESS")
aws_secret_key = os.getenv("SECACCESS")


MY_GUILD = discord.Object(id=1005671125646315530)
# Used disocrd docs to update sync
class client(discord.Client):
    def __init__(self, *, intents: discord.Intents):
        super().__init__(intents = intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self) -> None:
        self.tree.copy_global_to(guild=MY_GUILD)
        await self.tree.sync(guild=MY_GUILD)

intents = discord.Intents.default()
aclient = client(intents=intents)

@aclient.event
async def on_ready():
    print(f'Loggined in as {aclient.user} (ID: {aclient.user.id})')
    print('------')


async def get_demo_from_s3():
    demo_list = []
    prefix = "0/"
    session = aioboto3.Session()
    async with session.client('s3', aws_access_key_id=aws_access_key,
                             aws_secret_access_key=aws_secret_key, 
                             region_name=region, 
                             config=Config(signature_version='s3v4')) as s3_client:

        try:
            resp = await s3_client.list_objects_v2(
                Bucket=bucket,
                Prefix=prefix
            )
            for content in resp.get("Contents", []):
                demo_list.append(content["Key"])
            return demo_list
        except Exception as e:
            print(f"Error upload file to S3 bucket: {e}")

async def generate_presigned_url(file,channel):
    session = aioboto3.Session()

    async with session.client('s3', aws_access_key_id=aws_access_key,
                             aws_secret_access_key=aws_secret_key, 
                             region_name=region, 
                             config=Config(signature_version='s3v4')) as s3_client:
        try:
            url = await s3_client.generate_presigned_url(
                "get_object", Params={"Bucket":bucket, "Key":file}, ExpiresIn=25200
            )
            embed = discord.Embed(title="Demo File", description=f"[{file}]({url})")
            await channel.send(embed=embed)
        except ClientError as err: 
            print(err)
            raise
        return url

class DemoSelect(discord.ui.Select):
    """(https://gist.github.com/lykn/a2b68cb790d6dad8ecff75b2aa450f23) This was used to create drop down"""
    def __init__(self, demos):
        options = [discord.SelectOption(label=demo, value=demo) for demo in demos]
        super().__init__(placeholder="Select a demo file...", options=options)

    async def callback(self, interaction: discord.Interaction):
        """ This gets the value selected and initates the use of download demo and upload files """
        selected_demo = self.values[0]  # Get the selected demo
        await interaction.response.send_message(f"You selected: {selected_demo}", ephemeral=True)
        
        #This intstantly pulls the demo from s3 and returns a presigned url
        await generate_presigned_url(selected_demo, interaction.channel)
    


class SelectView(discord.ui.View):
    """This displays the dropdown"""
    def __init__(self, demos,*, timeout = 180):
        super().__init__(timeout=timeout)
        self.add_item(DemoSelect(demos))
                  

@aclient.tree.command(name="demo", description="Gets demos")
@app_commands.checks.cooldown(1, 100, key=lambda i: (i.user.id))
@app_commands.checks.has_role("demos")
async def demo(interaction: discord.Interaction):
    """Slash command that retrieves and displays demo files"""
    try:
        await interaction.response.send_message("Retrieving demo files... Please wait", ephemeral=True)
        demos =  await get_demo_from_s3()
        
        view = SelectView(demos)

        await interaction.followup.send("Select a file...", view=view, ephemeral=True)

        if not demos:
            await interaction.response.send_message("No demo files found.")
            return

    except Exception as e:
        await interaction.response.send_message(f"An error occurred: {str(e)}")

@aclient.tree.command(name="deletedemos", description="Deletes all the bots messages")
async def delete_demos(interaction: discord.Interaction):

    await interaction.response.send_message("Deleting bot messages please wait...", ephemeral=True)

    deleted = 0

    async for message in interaction.channel.history(limit=100):
        if message.author == aclient.user:
            await message.delete()
            await asyncio.sleep(2)
            deleted += 1
            print("Deleted messages.")
    if deleted > 0:
        await interaction.followup.send(f"deleted {deleted} messages", ephemeral=True)
    else:
        await interaction.followup.send("No messages found", ephemeral=True)

@aclient.tree.error
async def on_app_command_error(interaction:discord.Interaction, error: app_commands.AppCommandError):
    if isinstance(error, app_commands.CommandOnCooldown):
        msg = '**Still on cooldown**, please try again in {:.2f}s'.format(error.retry_after)
        await interaction.response.send_message(msg, ephemeral=True)
      
    
if __name__ == "__main__":
    aclient.run(api)